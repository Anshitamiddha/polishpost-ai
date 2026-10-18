package com.PublishPro_AI.workspace.authorization;

import com.PublishPro_AI.common.exception.ForbiddenException;
import com.PublishPro_AI.workspace.entity.WorkspaceMember;
import com.PublishPro_AI.workspace.repository.WorkspaceMemberRepository;
import com.PublishPro_AI.workspace.entity.WorkspaceRole;
import org.springframework.stereotype.Service;

@Service
public class WorkspaceAuthorizationService {

    private final WorkspaceMemberRepository workspaceMemberRepository;

    public WorkspaceAuthorizationService(
            WorkspaceMemberRepository workspaceMemberRepository
    ) {
        this.workspaceMemberRepository = workspaceMemberRepository;
    }

    public WorkspaceMember requireMember(
            Long workspaceId,
            Long userId
    ) {
        return workspaceMemberRepository
                .findByWorkspaceIdAndUserId(workspaceId, userId)
                .orElseThrow(() ->
                        new ForbiddenException(
                                "User is not a member of this workspace"
                        )
                );
    }
    public WorkspaceMember requireOwner(
            Long workspaceId,
            Long userId
    ) {
        WorkspaceMember membership =
                requireMember(workspaceId, userId);

        if (membership.getRole() != WorkspaceRole.OWNER) {
            throw new ForbiddenException(
                    "Only the workspace owner can perform this action"
            );
        }

        return membership;
    }
}
