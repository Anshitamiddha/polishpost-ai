package com.PublishPro_AI.thumbnail.dto;

import com.fasterxml.jackson.annotation.JsonAlias;

public record ThumbnailResponse(
        String status,
        ThumbnailImage image,
        @JsonAlias("provider_generation_id") String providerGenerationId,
        @JsonAlias("credits_charged") int creditsCharged
) {
}
