package com.PublishPro_AI.workspace.service;

import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;
import com.PublishPro_AI.workspace.authorization.WorkspaceAuthorizationService;
import com.PublishPro_AI.workspace.dto.CreateWorkspaceRequest;
import com.PublishPro_AI.workspace.dto.WorkspaceResponse;
import com.PublishPro_AI.workspace.entity.Workspace;
import com.PublishPro_AI.workspace.entity.WorkspaceMember;
import com.PublishPro_AI.workspace.entity.WorkspaceRole;
import com.PublishPro_AI.workspace.repository.WorkspaceMemberRepository;
import com.PublishPro_AI.workspace.repository.WorkspaceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class WorkspaceService {

    private final WorkspaceRepository workspaceRepository;
    private final WorkspaceMemberRepository workspaceMemberRepository;
    private final WorkspaceAuthorizationService authorizationService;
    private final UserRepository userRepository;

    public WorkspaceService(
            WorkspaceRepository workspaceRepository,
            WorkspaceMemberRepository workspaceMemberRepository,
            UserRepository userRepository,
            WorkspaceAuthorizationService authorizationService
    ) {
        this.workspaceRepository = workspaceRepository;
        this.workspaceMemberRepository = workspaceMemberRepository;
        this.userRepository = userRepository;
        this.authorizationService = authorizationService;
    }

    @Transactional
    public WorkspaceResponse createWorkspace(
            CreateWorkspaceRequest request,
            String userEmail
    ) {
        User owner = userRepository.findByEmail(userEmail)
                .orElseThrow(() ->
                        new IllegalArgumentException("User not found")
                );

        Workspace workspace = new Workspace();
        workspace.setName(request.getName().trim());
        workspace.setOwner(owner);

        Workspace savedWorkspace =
                workspaceRepository.save(workspace);

        WorkspaceMember ownerMembership = new WorkspaceMember();
        ownerMembership.setWorkspace(savedWorkspace);
        ownerMembership.setUser(owner);
        ownerMembership.setRole(WorkspaceRole.OWNER);

        workspaceMemberRepository.save(ownerMembership);

        return new WorkspaceResponse(
                savedWorkspace.getId(),
                savedWorkspace.getName(),
                owner.getId(),
                savedWorkspace.getCreatedAt(),
                savedWorkspace.getUpdatedAt()
        );
    }

    @Transactional(readOnly = true)
    public List<WorkspaceResponse> getMyWorkspaces(
            String userEmail
    ) {
        User user = userRepository.findByEmail(userEmail)
                .orElseThrow(() ->
                        new IllegalArgumentException("User not found")
                );

        return workspaceMemberRepository
                .findByUserId(user.getId())
                .stream()
                .map(WorkspaceMember::getWorkspace)
                .map(workspace -> new WorkspaceResponse(
                        workspace.getId(),
                        workspace.getName(),
                        workspace.getOwner().getId(),
                        workspace.getCreatedAt(),
                        workspace.getUpdatedAt()
                ))
                .toList();
    }

    @Transactional(readOnly = true)
    public WorkspaceResponse getWorkspace(
            Long workspaceId,
            String userEmail
    ) {
        User user = userRepository.findByEmail(userEmail)
                .orElseThrow(() ->
                        new IllegalArgumentException("User not found")
                );

        Workspace workspace = workspaceRepository.findById(workspaceId)
                .orElseThrow(() ->
                        new IllegalArgumentException("Workspace not found")
                );

        authorizationService.requireMember(
                workspaceId,
                user.getId()
        );

        return new WorkspaceResponse(
                workspace.getId(),
                workspace.getName(),
                workspace.getOwner().getId(),
                workspace.getCreatedAt(),
                workspace.getUpdatedAt()
        );
    }
}