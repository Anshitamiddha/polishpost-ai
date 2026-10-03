package com.PublishPro_AI.workspace.controller;

import com.PublishPro_AI.workspace.dto.CreateWorkspaceRequest;
import com.PublishPro_AI.workspace.dto.WorkspaceResponse;
import com.PublishPro_AI.workspace.service.WorkspaceService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/workspaces")
public class WorkspaceController {

    private final WorkspaceService workspaceService;

    public WorkspaceController(WorkspaceService workspaceService) {
        this.workspaceService = workspaceService;
    }

    @PostMapping
    public ResponseEntity<WorkspaceResponse> createWorkspace(
            @Valid @RequestBody CreateWorkspaceRequest request,
            Authentication authentication
    ) {
        String userEmail = authentication.getName();

        WorkspaceResponse response =
                workspaceService.createWorkspace(request, userEmail);

        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(response);
    }

    @GetMapping
    public ResponseEntity<List<WorkspaceResponse>> getMyWorkspaces(
            Authentication authentication
    ) {
        String userEmail = authentication.getName();

        List<WorkspaceResponse> response =
                workspaceService.getMyWorkspaces(userEmail);

        return ResponseEntity.ok(response);
    }

    @GetMapping("/{workspaceId}")
    public ResponseEntity<WorkspaceResponse> getWorkspace(
            @PathVariable Long workspaceId,
            Authentication authentication
    ) {
        String userEmail = authentication.getName();

        WorkspaceResponse response =
                workspaceService.getWorkspace(
                        workspaceId,
                        userEmail
                );

        return ResponseEntity.ok(response);
    }
}