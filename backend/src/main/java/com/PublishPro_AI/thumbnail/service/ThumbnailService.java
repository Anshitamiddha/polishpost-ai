package com.PublishPro_AI.thumbnail.service;

import com.PublishPro_AI.common.exception.AiServiceException;
import com.PublishPro_AI.common.exception.NotFoundException;
import com.PublishPro_AI.config.AiServiceProperties;
import com.PublishPro_AI.thumbnail.dto.GenerateThumbnailRequest;
import com.PublishPro_AI.thumbnail.dto.ThumbnailResponse;
import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;
import com.PublishPro_AI.workspace.authorization.WorkspaceAuthorizationService;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

/**
 * Asks the Python AI service for one thumbnail. This is the only place that
 * decides which workspace a picture belongs to: the AI service trusts the
 * workspace id it receives, so membership is checked here first.
 *
 * There is deliberately no @Transactional: the call can take minutes and
 * should not hold a database connection while it waits.
 */
@Service
public class ThumbnailService {

    private static final Logger log = LoggerFactory.getLogger(ThumbnailService.class);

    private static final String GENERATE_PATH = "/api/v1/publish/thumbnails";
    private static final String TOKEN_HEADER = "X-Internal-Service-Token";

    private final UserRepository userRepository;
    private final WorkspaceAuthorizationService authorizationService;
    private final RestClient aiServiceClient;
    private final AiServiceProperties properties;

    public ThumbnailService(
            UserRepository userRepository,
            WorkspaceAuthorizationService authorizationService,
            RestClient aiServiceClient,
            AiServiceProperties properties
    ) {
        this.userRepository = userRepository;
        this.authorizationService = authorizationService;
        this.aiServiceClient = aiServiceClient;
        this.properties = properties;
    }

    public ThumbnailResponse generate(
            Long workspaceId,
            GenerateThumbnailRequest request,
            String userEmail
    ) {
        User user = userRepository.findByEmail(userEmail)
                .orElseThrow(() -> new NotFoundException("User not found"));

        // Before anything is paid for, make sure the caller belongs here.
        authorizationService.requireMember(workspaceId, user.getId());

        String secret = properties.sharedSecret();
        if (secret == null || secret.isBlank()) {
            log.error("AI_SERVICE_SHARED_SECRET is not set");
            throw new AiServiceException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "The AI service is not configured."
            );
        }

        ThumbnailResponse response;
        try {
            response = aiServiceClient.post()
                    .uri(GENERATE_PATH)
                    .header(TOKEN_HEADER, secret)
                    .body(toAiRequest(workspaceId, request))
                    .retrieve()
                    .body(ThumbnailResponse.class);
        } catch (RestClientResponseException exception) {
            throw toAiServiceException(exception);
        } catch (ResourceAccessException exception) {
            log.warn("Could not reach the AI service: {}", exception.getMessage());
            throw new AiServiceException(
                    HttpStatus.SERVICE_UNAVAILABLE,
                    "The AI service is not reachable right now. Please try again."
            );
        } catch (RestClientException exception) {
            // A success answer we could not read, such as one missing a field.
            log.warn("The AI service sent an answer this backend cannot read: {}", exception.getMessage());
            throw new AiServiceException(
                    HttpStatus.BAD_GATEWAY,
                    "The AI service returned an unusable answer."
            );
        }

        if (response == null || response.image() == null) {
            throw new AiServiceException(
                    HttpStatus.BAD_GATEWAY,
                    "The AI service returned an unusable answer."
            );
        }

        return response;
    }

    /*
     * The page and the AI service use the same field names, so this only adds
     * the workspace (from the URL, never from the body) and tidies the text.
     * The description and the global prompt are optional, so a blank one is
     * left out instead of being sent as empty text.
     */
    private AiThumbnailRequest toAiRequest(
            Long workspaceId,
            GenerateThumbnailRequest request
    ) {
        return new AiThumbnailRequest(
                workspaceId,
                request.videoTopic().trim(),
                blankToNull(request.description()),
                blankToNull(request.globalPrompt())
        );
    }

    private String blankToNull(String text) {
        if (text == null || text.isBlank()) {
            return null;
        }

        return text.trim();
    }

    private AiServiceException toAiServiceException(
            RestClientResponseException exception
    ) {
        int status = exception.getStatusCode().value();

        // Only the status is logged. The AI service's texts are safe to show,
        // but a log line does not need them.
        log.warn("The AI service answered with HTTP {}", status);

        if (status == 429) {
            return new AiServiceException(
                    HttpStatus.TOO_MANY_REQUESTS,
                    detailOf(exception, "The AI service is busy right now. Please try again later.")
            );
        }

        if (status >= 500) {
            HttpStatus same = HttpStatus.resolve(status);
            return new AiServiceException(
                    same != null ? same : HttpStatus.BAD_GATEWAY,
                    detailOf(exception, "The AI service could not make the thumbnail. Please try again.")
            );
        }

        if (status == 401 || status == 403) {
            log.error("The AI service refused this backend's token. Check AI_SERVICE_SHARED_SECRET.");
            return new AiServiceException(
                    HttpStatus.BAD_GATEWAY,
                    "The AI service is not set up correctly."
            );
        }

        // The AI service names the field that failed, so this one is worth a log line.
        log.warn("The AI service rejected the request: {}", String.format("%.300s", exception.getResponseBodyAsString()));

        return new AiServiceException(
                HttpStatus.BAD_REQUEST,
                "The AI service did not accept the request. Check the video topic, description and global prompt."
        );
    }

    // The AI service answers errors as {"detail": "text"}.
    private String detailOf(RestClientResponseException exception, String fallback) {
        try {
            ErrorBody body = exception.getResponseBodyAs(ErrorBody.class);
            if (body != null && body.detail() != null && !body.detail().isBlank()) {
                return body.detail();
            }
        } catch (RuntimeException unreadable) {
            // Not the shape we expected (for example a proxy's error page): use the fallback.
        }

        return fallback;
    }

    private record ErrorBody(String detail) {
    }

    // The AI service's request, with its snake_case names. Null fields are left out.
    @JsonInclude(JsonInclude.Include.NON_NULL)
    record AiThumbnailRequest(
            @JsonProperty("workspace_id") Long workspaceId,
            @JsonProperty("video_topic") String videoTopic,
            String description,
            @JsonProperty("global_prompt") String globalPrompt
    ) {
    }
}
