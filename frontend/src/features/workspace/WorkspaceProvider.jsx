import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../lib/apiClient";
import { useAuth } from "../auth/useAuth";
import AddMemberModal from "./AddMemberModal";
import CreateWorkspaceModal from "./CreateWorkspaceModal";
import {
  addMemberRequest,
  createWorkspaceRequest,
  fetchWorkspaces,
} from "./workspaceApi";
import { WorkspaceContext } from "./workspaceContext";

// Which workspace was last selected is a per-user convenience, so it is kept
// in localStorage (the login token stays in sessionStorage).
function storageKey(userId) {
  return `publishpro.workspace.${userId}`;
}

function readSavedId(userId) {
  try {
    return localStorage.getItem(storageKey(userId));
  } catch {
    return null;
  }
}

function saveId(userId, id) {
  try {
    localStorage.setItem(storageKey(userId), String(id));
  } catch {
    // Storage unavailable: the selection just won't survive a refresh.
  }
}

/*
 * status:
 *   "loading"  GET /api/workspaces is in flight
 *   "ready"    `workspaces` is the list (it can be empty for a new user)
 *   "error"    the list could not be loaded; reload() tries again
 *
 * Mounted inside the protected layout, so it only exists while someone is
 * logged in and starts from scratch for the next login.
 */
function WorkspaceProvider({ children }) {
  const { user } = useAuth();
  const userId = user?.id;

  const [workspaces, setWorkspaces] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(() => readSavedId(userId));
  const [attempt, setAttempt] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  // The workspace the "Add member" dialog is open for (null = closed).
  const [addMemberTarget, setAddMemberTarget] = useState(null);
  // Goes up every time a member is added, so a visible members list knows
  // to load again.
  const [membersVersion, setMembersVersion] = useState(0);

  useEffect(() => {
    let ignore = false;

    fetchWorkspaces()
      .then((list) => {
        if (!ignore) {
          setWorkspaces(list);
          setStatus("ready");
        }
      })
      .catch((err) => {
        // A 401 has already ended the session (see apiClient).
        if (ignore || (err instanceof ApiError && err.status === 401)) {
          return;
        }

        setError(err.message);
        setStatus("error");
      });

    return () => {
      ignore = true;
    };
  }, [attempt]);

  // A saved id can point at a workspace the user no longer belongs to, so
  // fall back to the first one instead of showing nothing.
  const selectedWorkspace = useMemo(
    () =>
      workspaces.find((workspace) => String(workspace.id) === selectedId) ??
      workspaces[0] ??
      null,
    [workspaces, selectedId]
  );

  const selectWorkspace = useCallback(
    (id) => {
      setSelectedId(String(id));
      saveId(userId, id);
    },
    [userId]
  );

  const createWorkspace = useCallback(
    async (name) => {
      const created = await createWorkspaceRequest(name);

      setWorkspaces((previous) => [...previous, created]);
      selectWorkspace(created.id);

      return created;
    },
    [selectWorkspace]
  );

  const addMember = useCallback(async (workspaceId, email) => {
    await addMemberRequest(workspaceId, email);
    setMembersVersion((previous) => previous + 1);
  }, []);

  const reload = useCallback(() => {
    setError("");
    setStatus("loading");
    setAttempt((previous) => previous + 1);
  }, []);

  const openCreateWorkspace = useCallback(() => setIsCreateOpen(true), []);
  const closeCreateWorkspace = useCallback(() => setIsCreateOpen(false), []);
  const openAddMember = useCallback(
    (workspace) => setAddMemberTarget(workspace),
    []
  );
  const closeAddMember = useCallback(() => setAddMemberTarget(null), []);

  const value = useMemo(
    () => ({
      workspaces,
      status,
      error,
      selectedWorkspace,
      membersVersion,
      selectWorkspace,
      createWorkspace,
      reload,
      openCreateWorkspace,
      openAddMember,
    }),
    [
      workspaces,
      status,
      error,
      selectedWorkspace,
      membersVersion,
      selectWorkspace,
      createWorkspace,
      reload,
      openCreateWorkspace,
      openAddMember,
    ]
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}

      {isCreateOpen && (
        <CreateWorkspaceModal
          onCreate={createWorkspace}
          onClose={closeCreateWorkspace}
        />
      )}

      {addMemberTarget && (
        <AddMemberModal
          workspace={addMemberTarget}
          onAdd={addMember}
          onClose={closeAddMember}
        />
      )}
    </WorkspaceContext.Provider>
  );
}

export default WorkspaceProvider;
