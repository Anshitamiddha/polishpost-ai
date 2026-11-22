package com.PublishPro_AI.thumbnail.dto;

import com.fasterxml.jackson.annotation.JsonAlias;

/**
 * The stored picture. objectKey says where it is in the private bucket. It is
 * not a link. The aliases are the AI service's snake_case names.
 */
public record ThumbnailImage(
        int width,
        int height,
        String format,
        @JsonAlias("asset_id") String assetId,
        @JsonAlias("object_key") String objectKey,
        @JsonAlias("content_type") String contentType,
        @JsonAlias("size_bytes") long sizeBytes
) {
}
