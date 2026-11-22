package com.PublishPro_AI.thumbnail.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * What the Create Post page sends. The limits match the AI service's, so a
 * request that passes here is accepted there.
 */
public record GenerateThumbnailRequest(

        @NotBlank(message = "Title is required")
        @Size(min = 3, max = 60, message = "Title must be between 3 and 60 characters")
        String title,

        @Size(max = 300, message = "Description must not exceed 300 characters")
        String description,

        // The global creative prompt. Optional: the user may clear it.
        @Size(max = 500, message = "Creative prompt must not exceed 500 characters")
        String prompt
) {
}
