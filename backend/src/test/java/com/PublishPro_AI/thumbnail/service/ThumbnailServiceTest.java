package com.PublishPro_AI.thumbnail.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withException;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import java.io.IOException;
import java.time.Duration;
import java.util.Optional;

import com.PublishPro_AI.common.exception.AiServiceException;
import com.PublishPro_AI.common.exception.ForbiddenException;
import com.PublishPro_AI.common.exception.NotFoundException;
import com.PublishPro_AI.config.AiServiceProperties;
import com.PublishPro_AI.thumbnail.dto.GenerateThumbnailRequest;
import com.PublishPro_AI.thumbnail.dto.ThumbnailResponse;
import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;
import com.PublishPro_AI.workspace.authorization.WorkspaceAuthorizationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

/*
 * These tests stand in for the AI service with MockRestServiceServer, so
 * nothing leaves this computer and no credits are spent. They check what this
 * backend sends, and that it never sends anything for a stranger.
 */
class ThumbnailServiceTest {

    private static final String BASE_URL = "http://ai.test";
    private static final String GENERATE_URL = BASE_URL + "/api/v1/publish/thumbnails";
    // Made up for these tests only.
    private static final String SECRET = "test-shared-secret";
    private static final String EMAIL = "me@example.com";
    private static final Long WORKSPACE_ID = 12L;

    private static final String PROMPT =
            "Create a bold, cinematic YouTube thumbnail. Keep the creator as the "
                    + "main focus, use dramatic lighting, strong contrast, and leave "
                    + "space for a short headline.";

    private static final String AI_ANSWER = """
            {"success": true, "status": "complete",
             "image": {"reference": "a1.png", "width": 640, "height": 360, "format": "png",
                       "asset_id": "a1", "object_key": "workspaces/12/generated/a1.png",
                       "content_type": "image/png", "size_bytes": 1234},
             "provider_generation_id": "job-1", "credits_charged": 5}
            """;

    private final UserRepository userRepository = mock(UserRepository.class);
    private final WorkspaceAuthorizationService authorization =
            mock(WorkspaceAuthorizationService.class);

    private MockRestServiceServer aiService;
    private ThumbnailService service;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl(BASE_URL);
        aiService = MockRestServiceServer.bindTo(builder).build();
        service = serviceWithSecret(builder.build(), SECRET);

        User user = new User();
        user.setId(7L);
        when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(user));
    }

    private ThumbnailService serviceWithSecret(RestClient client, String secret) {
        return new ThumbnailService(
                userRepository,
                authorization,
                client,
                new AiServiceProperties(BASE_URL, secret, Duration.ofSeconds(5))
        );
    }

    private GenerateThumbnailRequest request(String description, String prompt) {
        return new GenerateThumbnailRequest("AI APP IN 7 DAYS", description, prompt);
    }

    // --- the global creative prompt reaches the AI service ---------------------

    @Test
    void theGlobalPromptIsSentToTheAiServiceExactlyAsWritten() {
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Internal-Service-Token", SECRET))
                .andExpect(jsonPath("$.visual_style").value(PROMPT))
                .andExpect(jsonPath("$.heading").value("AI APP IN 7 DAYS"))
                .andExpect(jsonPath("$.video_topic").value("I built a full AI app in seven days"))
                .andExpect(jsonPath("$.workspace_id").value(12))
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        ThumbnailResponse response = service.generate(
                WORKSPACE_ID,
                request("I built a full AI app in seven days", PROMPT),
                EMAIL
        );

        aiService.verify();
        assertEquals("workspaces/12/generated/a1.png", response.image().objectKey());
        assertEquals("a1", response.image().assetId());
        assertEquals("image/png", response.image().contentType());
        assertEquals(1234, response.image().sizeBytes());
        assertEquals(5, response.creditsCharged());
        assertEquals("job-1", response.providerGenerationId());
    }

    @Test
    void oneRequestMakesOneCallThatAsksForNoNumberOfPictures() {
        aiService.expect(requestTo(GENERATE_URL))
                // Only these four fields: nothing in the request can ask for more than one picture.
                .andExpect(jsonPath("$.length()").value(4))
                .andExpect(jsonPath("$.image_count").doesNotExist())
                .andExpect(jsonPath("$.count").doesNotExist())
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        ThumbnailResponse response = service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL);

        aiService.verify(); // exactly one call was made, and it was the expected one
        assertEquals("a1", response.image().assetId());
    }

    @Test
    void aDifferentPromptGivesADifferentRequest() {
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(jsonPath("$.visual_style").value("soft pastel colors"))
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        service.generate(WORKSPACE_ID, request("a video", "soft pastel colors"), EMAIL);

        aiService.verify();
    }

    @Test
    void surroundingSpacesAreTrimmedFromThePrompt() {
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(jsonPath("$.visual_style").value("neon city"))
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        service.generate(WORKSPACE_ID, request("a video", "   neon city  "), EMAIL);

        aiService.verify();
    }

    @Test
    void aBlankOrMissingPromptIsLeftOutOfTheRequest() {
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(jsonPath("$.visual_style").doesNotExist())
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(jsonPath("$.visual_style").doesNotExist())
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        service.generate(WORKSPACE_ID, request("a video", "   "), EMAIL);
        service.generate(WORKSPACE_ID, request("a video", null), EMAIL);

        aiService.verify();
    }

    @Test
    void theTitleStandsInWhenThereIsNoDescription() {
        aiService.expect(requestTo(GENERATE_URL))
                .andExpect(jsonPath("$.video_topic").value("AI APP IN 7 DAYS"))
                .andExpect(jsonPath("$.heading").value("AI APP IN 7 DAYS"))
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        service.generate(WORKSPACE_ID, request("  ", PROMPT), EMAIL);

        aiService.verify();
    }

    // --- only members of the workspace may spend its credits -----------------------

    @Test
    void aNonMemberGetsForbiddenAndNothingIsSent() {
        doThrow(new ForbiddenException("User is not a member of this workspace"))
                .when(authorization).requireMember(WORKSPACE_ID, 7L);

        assertThrows(
                ForbiddenException.class,
                () -> service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL)
        );

        aiService.verify(); // no request was expected, so none may have been made
    }

    @Test
    void theMembershipIsCheckedForTheWorkspaceInTheUrl() {
        aiService.expect(requestTo(GENERATE_URL))
                .andRespond(withSuccess(AI_ANSWER, MediaType.APPLICATION_JSON));

        service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL);

        verify(authorization).requireMember(WORKSPACE_ID, 7L);
    }

    @Test
    void anUnknownUserIsNotFoundAndNothingIsChecked() {
        assertThrows(
                NotFoundException.class,
                () -> service.generate(WORKSPACE_ID, request("a video", PROMPT), "nobody@example.com")
        );

        verifyNoInteractions(authorization);
        aiService.verify();
    }

    // --- the AI service says no --------------------------------------------------------

    private AiServiceException failWith(HttpStatus status, String body) {
        aiService.expect(requestTo(GENERATE_URL))
                .andRespond(withStatus(status)
                        .contentType(MediaType.APPLICATION_JSON)
                        .body(body));

        return assertThrows(
                AiServiceException.class,
                () -> service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL)
        );
    }

    @Test
    void aRateLimitKeepsItsStatusAndText() {
        AiServiceException error =
                failWith(HttpStatus.TOO_MANY_REQUESTS, "{\"detail\": \"The AI service is busy.\"}");

        assertEquals(HttpStatus.TOO_MANY_REQUESTS, error.getStatus());
        assertEquals("The AI service is busy.", error.getMessage());
    }

    @Test
    void aStorageFailureAfterGenerationKeepsItsSafeText() {
        AiServiceException error = failWith(
                HttpStatus.SERVICE_UNAVAILABLE,
                "{\"detail\": \"The thumbnail was generated, but it could not be stored.\"}"
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, error.getStatus());
        assertEquals("The thumbnail was generated, but it could not be stored.", error.getMessage());
    }

    @Test
    void aServerErrorWithAnUnreadableBodyGetsASafeFallback() {
        AiServiceException error = failWith(HttpStatus.BAD_GATEWAY, "<html>proxy error</html>");

        assertEquals(HttpStatus.BAD_GATEWAY, error.getStatus());
        assertEquals("The AI service could not make the thumbnail. Please try again.", error.getMessage());
    }

    @Test
    void aRejectedRequestIsABadRequestWithoutTheRawDetails() {
        // FastAPI answers a validation problem with a list, not a text.
        AiServiceException error = failWith(
                HttpStatus.UNPROCESSABLE_ENTITY,
                "{\"detail\": [{\"loc\": [\"body\", \"heading\"], \"msg\": \"too short\"}]}"
        );

        assertEquals(HttpStatus.BAD_REQUEST, error.getStatus());
        assertEquals(
                "The AI service did not accept the request. Check the title, description and prompt.",
                error.getMessage()
        );
    }

    @Test
    void aRefusedTokenIsOurSetupProblemAndNotTheUsers() {
        AiServiceException error = failWith(HttpStatus.UNAUTHORIZED, "{\"detail\": \"Missing or invalid service token.\"}");

        assertEquals(HttpStatus.BAD_GATEWAY, error.getStatus());
        assertEquals("The AI service is not set up correctly.", error.getMessage());
    }

    @Test
    void anUnreachableAiServiceIsATemporaryOutage() {
        aiService.expect(requestTo(GENERATE_URL))
                .andRespond(withException(new IOException("Connection refused")));

        AiServiceException error = assertThrows(
                AiServiceException.class,
                () -> service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL)
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, error.getStatus());
        assertEquals("The AI service is not reachable right now. Please try again.", error.getMessage());
    }

    @Test
    void anAnswerWithoutAPictureIsRefused() {
        aiService.expect(requestTo(GENERATE_URL))
                .andRespond(withSuccess("{\"status\": \"complete\"}", MediaType.APPLICATION_JSON));

        AiServiceException error = assertThrows(
                AiServiceException.class,
                () -> service.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL)
        );

        assertEquals(HttpStatus.BAD_GATEWAY, error.getStatus());
    }

    // --- the shared secret -----------------------------------------------------------------

    @Test
    void withoutASharedSecretNothingIsSent() {
        ThumbnailService unconfigured = serviceWithSecret(RestClient.builder().baseUrl(BASE_URL).build(), "  ");

        AiServiceException error = assertThrows(
                AiServiceException.class,
                () -> unconfigured.generate(WORKSPACE_ID, request("a video", PROMPT), EMAIL)
        );

        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, error.getStatus());
        assertEquals("The AI service is not configured.", error.getMessage());
    }

    @Test
    void theSecretNeverAppearsInAnErrorMessage() {
        AiServiceException error = failWith(HttpStatus.UNAUTHORIZED, "{\"detail\": \"" + SECRET + "\"}");

        assertFalse(error.getMessage().contains(SECRET));
    }
}
