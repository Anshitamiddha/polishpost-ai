package com.PublishPro_AI.thumbnail.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.security.Principal;

import com.PublishPro_AI.common.exception.AiServiceException;
import com.PublishPro_AI.common.exception.ForbiddenException;
import com.PublishPro_AI.common.exception.GlobalExceptionHandler;
import com.PublishPro_AI.thumbnail.dto.GenerateThumbnailRequest;
import com.PublishPro_AI.thumbnail.dto.ThumbnailImage;
import com.PublishPro_AI.thumbnail.dto.ThumbnailResponse;
import com.PublishPro_AI.thumbnail.service.ThumbnailService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

/*
 * The controller on its own, without Spring Security or a database: the URL,
 * the validation messages, who the caller is, and how errors look to the page.
 */
class ThumbnailControllerTest {

    private static final String URL = "/api/workspaces/12/thumbnails";
    private static final Principal CALLER =
            new UsernamePasswordAuthenticationToken("me@example.com", null);

    private final ThumbnailService service = mock(ThumbnailService.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders
                .standaloneSetup(new ThumbnailController(service))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    private org.springframework.test.web.servlet.ResultActions send(String json) throws Exception {
        return mvc.perform(post(URL)
                .principal(CALLER)
                .contentType(MediaType.APPLICATION_JSON)
                .content(json));
    }

    @Test
    void thePagesPromptAndTheWorkspaceInTheUrlReachTheService() throws Exception {
        ThumbnailResponse answer = new ThumbnailResponse(
                "complete",
                new ThumbnailImage(640, 360, "png", "a1", "workspaces/12/generated/a1.png", "image/png", 1234),
                "job-1",
                5
        );
        when(service.generate(eq(12L), any(), eq("me@example.com"))).thenReturn(answer);

        send("""
                {"title": "AI APP IN 7 DAYS", "description": "I built an app", "prompt": "neon city"}
                """)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.image.objectKey").value("workspaces/12/generated/a1.png"))
                .andExpect(jsonPath("$.creditsCharged").value(5));

        verify(service).generate(
                12L,
                new GenerateThumbnailRequest("AI APP IN 7 DAYS", "I built an app", "neon city"),
                "me@example.com"
        );
    }

    @Test
    void aNumberOfThumbnailsSentByTheClientIsIgnoredAndOneImageComesBack() throws Exception {
        ThumbnailResponse answer = new ThumbnailResponse(
                "complete",
                new ThumbnailImage(640, 360, "png", "a1", "workspaces/12/generated/a1.png", "image/png", 1234),
                "job-1",
                5
        );
        when(service.generate(any(), any(), any())).thenReturn(answer);

        send("""
                {"title": "A good title", "count": 3, "variations": 3, "imageCount": 3}
                """)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.image.objectKey").value("workspaces/12/generated/a1.png"))
                .andExpect(jsonPath("$.images").doesNotExist());

        // The service only ever sees the three fields it knows, so no count can travel on.
        verify(service).generate(
                12L,
                new GenerateThumbnailRequest("A good title", null, null),
                "me@example.com"
        );
    }

    @Test
    void aBadRequestIsRefusedWithTheFirstMessageAndNothingIsGenerated() throws Exception {
        send("""
                {"title": "ab", "prompt": "neon city"}
                """)
                .andExpect(status().isBadRequest())
                .andExpect(content().string("Title must be between 3 and 60 characters"));

        verifyNoInteractions(service);
    }

    @Test
    void aMissingTitleIsRefused() throws Exception {
        send("{\"prompt\": \"neon city\"}")
                .andExpect(status().isBadRequest())
                .andExpect(content().string("Title is required"));

        verifyNoInteractions(service);
    }

    @Test
    void aNonMemberSeesForbidden() throws Exception {
        when(service.generate(any(), any(), any()))
                .thenThrow(new ForbiddenException("User is not a member of this workspace"));

        send("{\"title\": \"A good title\"}")
                .andExpect(status().isForbidden())
                .andExpect(content().string("User is not a member of this workspace"));
    }

    @Test
    void anAiServiceFailureReachesThePageWithItsStatusAndSafeText() throws Exception {
        when(service.generate(any(), any(), any())).thenThrow(new AiServiceException(
                HttpStatus.SERVICE_UNAVAILABLE,
                "The thumbnail was generated, but it could not be stored."
        ));

        send("{\"title\": \"A good title\"}")
                .andExpect(status().isServiceUnavailable())
                .andExpect(content().string("The thumbnail was generated, but it could not be stored."));
    }
}
