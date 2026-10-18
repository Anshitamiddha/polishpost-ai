import { ApiError, apiRequest } from "../../lib/apiClient";

// GET /api/workspaces
//   -> WorkspaceResponse[] { id, name, ownerId, createdAt, updatedAt }
// Only the workspaces the logged-in user belongs to.
export function fetchWorkspaces() {
  return apiRequest("/api/workspaces", { auth: true });
}

// POST /api/workspaces { name } -> 201 WorkspaceResponse
// The caller becomes the workspace's OWNER.
export function createWorkspaceRequest(name) {
  return apiRequest("/api/workspaces", {
    method: "POST",
    body: { name },
    auth: true,
  });
}

// GET /api/workspaces/{id}/members
//   -> WorkspaceMemberResponse[] { userId, name, email, role, joinedAt }
// role is "OWNER" or "EDITOR". 403 if the caller is not a member.
export function fetchMembers(workspaceId) {
  return apiRequest(`/api/workspaces/${workspaceId}/members`, { auth: true });
}

// POST /api/workspaces/{id}/members { email } -> 201, no body
// Owner only. The new member always joins as EDITOR. The person must already
// have an account: 404 "User not found" if not, 409 if already a member.
export async function addMemberRequest(workspaceId, email) {
  try {
    await apiRequest(`/api/workspaces/${workspaceId}/members`, {
      method: "POST",
      body: { email },
      auth: true,
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      throw new ApiError(
        "No PublishPro-AI account uses that email. Ask them to sign up first.",
        404
      );
    }

    throw err;
  }
}
