package com.PublishPro_AI.workspace.service;

import com.PublishPro_AI.common.exception.ConflictException;
import com.PublishPro_AI.common.exception.NotFoundException;
import com.PublishPro_AI.user.entity.User;
import com.PublishPro_AI.user.repository.UserRepository;
import com.PublishPro_AI.workspace.authorization.WorkspaceAuthorizationService;
import com.PublishPro_AI.workspace.dto.AddMemberRequest;
import com.PublishPro_AI.workspace.dto.CreateWorkspaceRequest;
import com.PublishPro_AI.workspace.dto.WorkspaceMemberResponse;
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

    @Transactional
    public void addMember(
            Long workspaceId,
            AddMemberRequest request,
            String ownerEmail
    ) {
        User owner = userRepository.findByEmail(ownerEmail)
                .orElseThrow(() ->
                        new IllegalArgumentException("User not found")
                );

        authorizationService.requireOwner(
                workspaceId,
                owner.getId()
        );

        User userToAdd = userRepository.findByEmail(
                request.getEmail().trim().toLowerCase()
        ).orElseThrow(() ->
                new NotFoundException("User not found")
        );

        if (workspaceMemberRepository.existsByWorkspaceIdAndUserId(
                workspaceId,
                userToAdd.getId()
        )) {
            throw new ConflictException(
                    "User is already a member of this workspace"
            );
        }

        Workspace workspace = workspaceRepository.findById(workspaceId)
                .orElseThrow(() ->
                        new NotFoundException("Workspace not found")
                );

        WorkspaceMember member = new WorkspaceMember();

        member.setWorkspace(workspace);
        member.setUser(userToAdd);
        member.setRole(WorkspaceRole.EDITOR);

        workspaceMemberRepository.save(member);
    }

    @Transactional(readOnly = true)
    public List<WorkspaceMemberResponse> getMembers(
            Long workspaceId,
            String userEmail
    ) {
        User user = userRepository.findByEmail(userEmail)
                .orElseThrow(() ->
                        new NotFoundException("User not found")
                );

        authorizationService.requireMember(
                workspaceId,
                user.getId()
        );

        return workspaceMemberRepository
                .findByWorkspaceId(workspaceId)
                .stream()
                .map(member -> new WorkspaceMemberResponse(
                        member.getUser().getId(),
                        member.getUser().getName(),
                        member.getUser().getEmail(),
                        member.getRole(),
                        member.getJoinedAt()
                ))
                .toList();
    }
}