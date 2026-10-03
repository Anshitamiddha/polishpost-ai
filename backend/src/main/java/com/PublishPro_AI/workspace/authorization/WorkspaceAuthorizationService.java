package com.PublishPro_AI.workspace.authorization;

import com.PublishPro_AI.workspace.entity.WorkspaceMember;
import com.PublishPro_AI.workspace.repository.WorkspaceMemberRepository;
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
                        new IllegalArgumentException(
                                "User is not a member of this workspace"
                        )
                );
    }
}
