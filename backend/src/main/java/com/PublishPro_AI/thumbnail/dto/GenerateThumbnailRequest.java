package com.PublishPro_AI.thumbnail.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * What the Create Post page sends. The field names and limits are the AI
 * service's, so a request that passes here is accepted there.
 * (The workspace is not here: it comes from the URL, so a client cannot
 * claim someone else's.)
 */
public record GenerateThumbnailRequest(

        // The video's title. The AI service also writes it on the picture.
        @JsonProperty("video_topic")
        @NotBlank(message = "Video topic is required")
        @Size(min = 3, max = 60, message = "Video topic must be between 3 and 60 characters")
        String videoTopic,

        @Size(max = 300, message = "Description must not exceed 300 characters")
        String description,

        // The global creative prompt. Optional: the user may clear it.
        @JsonProperty("global_prompt")
        @Size(max = 500, message = "Global prompt must not exceed 500 characters")
        String globalPrompt
) {
}
