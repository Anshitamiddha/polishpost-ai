package com.PublishPro_AI.thumbnail.controller;

import com.PublishPro_AI.thumbnail.dto.GenerateThumbnailRequest;
import com.PublishPro_AI.thumbnail.dto.ThumbnailResponse;
import com.PublishPro_AI.thumbnail.service.ThumbnailService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/workspaces/{workspaceId}/thumbnails")
public class ThumbnailController {

    private final ThumbnailService thumbnailService;

    public ThumbnailController(ThumbnailService thumbnailService) {
        this.thumbnailService = thumbnailService;
    }

    @PostMapping
    public ResponseEntity<ThumbnailResponse> generateThumbnail(
            @PathVariable Long workspaceId,
            @Valid @RequestBody GenerateThumbnailRequest request,
            Authentication authentication
    ) {
        String userEmail = authentication.getName();

        ThumbnailResponse response =
                thumbnailService.generate(workspaceId, request, userEmail);

        return ResponseEntity.ok(response);
    }
}
