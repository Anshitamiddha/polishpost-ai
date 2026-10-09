package com.PublishPro_AI.workspace.dto;

import com.PublishPro_AI.workspace.entity.WorkspaceRole;

import java.time.LocalDateTime;

public class WorkspaceMemberResponse {

    private Long userId;
    private String name;
    private String email;
    private WorkspaceRole role;
    private LocalDateTime joinedAt;

    public WorkspaceMemberResponse() {
    }

    public WorkspaceMemberResponse(
            Long userId,
            String name,
            String email,
            WorkspaceRole role,
            LocalDateTime joinedAt
    ) {
        this.userId = userId;
        this.name = name;
        this.email = email;
        this.role = role;
        this.joinedAt = joinedAt;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public WorkspaceRole getRole() {
        return role;
    }

    public void setRole(WorkspaceRole role) {
        this.role = role;
    }

    public LocalDateTime getJoinedAt() {
        return joinedAt;
    }

    public void setJoinedAt(LocalDateTime joinedAt) {
        this.joinedAt = joinedAt;
    }
}