import { useEffect, useState } from "react";

import { ApiError } from "../../lib/apiClient";
import { getInitials } from "../../lib/getInitials";
import { useAuth } from "../auth/useAuth";
import { useWorkspace } from "../workspace/useWorkspace";
import { fetchMembers } from "../workspace/workspaceApi";
import "./team.css";

const ROLE_LABELS = { OWNER: "Owner", EDITOR: "Editor" };

// The backend returns a LocalDateTime such as "2026-10-18T08:50:00.123".
function formatJoined(value) {
  const date = new Date(value);

  if (!value || Number.isNaN(date.getTime())) {
    return "—";
  }

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Owner first, then alphabetical.
function sortMembers(members) {
  const rank = (member) => (member.role === "OWNER" ? 0 : 1);

  return members
    .slice()
    .sort(
      (a, b) =>
        rank(a) - rank(b) || (a.name ?? "").localeCompare(b.name ?? "")
    );
}

// Rendered with key={workspace.id}, so switching workspace starts it fresh.
function MembersSection({ workspace }) {
  const { user } = useAuth();
  const { membersVersion } = useWorkspace();
  const [members, setMembers] = useState([]);
  const [status, setStatus] = useState("loading");
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);

  // Only the owner may add members (the backend enforces it too).
  const isOwner = workspace.ownerId === user.id;

  // Loads again when the workspace changes, on "Try again", and whenever a
  // member is added (from this page or from the sidebar).
  useEffect(() => {
    let ignore = false;

    fetchMembers(workspace.id)
      .then((list) => {
        if (!ignore) {
          setMembers(list);
          setStatus("ready");
        }
      })
      .catch((err) => {
        if (ignore || (err instanceof ApiError && err.status === 401)) {
          return;
        }

        setLoadError(err.message);
        setStatus("error");
      });

    return () => {
      ignore = true;
    };
  }, [workspace.id, attempt, membersVersion]);

  function retry() {
    setLoadError("");
    setStatus("loading");
    setAttempt((previous) => previous + 1);
  }

  return (
    <>
      {!isOwner && (
        <p className="team-note">
          Only the workspace owner can add members to {workspace.name}.
        </p>
      )}

      <section className="team-card" aria-labelledby="members-title">
        <div className="team-card-header">
          <h2 id="members-title">Members</h2>

          {status === "ready" && (
            <span className="team-count">{members.length}</span>
          )}
        </div>

        {status === "loading" && (
          <p className="team-state" role="status">
            Loading members...
          </p>
        )}

        {status === "error" && (
          <div className="team-state" role="alert">
            <p>{loadError}</p>
            <button type="button" className="team-button secondary" onClick={retry}>
              Try again
            </button>
          </div>
        )}

        {status === "ready" && (
          <table className="team-table">
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col">Role</th>
                <th scope="col" className="team-col-joined">
                  Joined
                </th>
              </tr>
            </thead>

            <tbody>
              {sortMembers(members).map((member) => (
                <tr key={member.userId}>
                  <td>
                    <div className="team-member">
                      <span
                        className={`team-avatar${
                          member.role === "OWNER" ? " owner" : ""
                        }`}
                        aria-hidden="true"
                      >
                        {getInitials(member.name)}
                      </span>

                      <span className="team-member-text">
                        <span className="team-member-name">
                          {member.name}
                          {member.userId === user.id && (
                            <span className="team-you">You</span>
                          )}
                        </span>
                        <span className="team-member-email">
                          {member.email}
                        </span>
                      </span>
                    </div>
                  </td>

                  <td>
                    <span
                      className={`role-badge ${String(member.role).toLowerCase()}`}
                    >
                      {ROLE_LABELS[member.role] ?? member.role}
                    </span>
                  </td>

                  <td className="team-col-joined">
                    {formatJoined(member.joinedAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}

// The Team screen (route /team): members of the selected workspace.
function TeamPage() {
  const { user } = useAuth();
  const {
    status,
    error,
    reload,
    selectedWorkspace,
    openCreateWorkspace,
    openAddMember,
  } = useWorkspace();

  let subtitle = "Manage who can work in your workspace.";
  let body;

  if (status === "loading") {
    subtitle = "Loading your workspaces...";
    body = (
      <p className="team-card team-state" role="status">
        Loading your workspaces...
      </p>
    );
  } else if (status === "error") {
    body = (
      <div className="team-card team-state" role="alert">
        <p>{error}</p>
        <button type="button" className="team-button secondary" onClick={reload}>
          Try again
        </button>
      </div>
    );
  } else if (!selectedWorkspace) {
    subtitle = "Create a workspace to start working with others.";
    body = (
      <div className="team-card team-empty">
        <h2>You don't have a workspace yet</h2>
        <p>
          Workspaces hold your content and your team. Create one, then add
          teammates by email.
        </p>
        <button
          type="button"
          className="team-button primary"
          onClick={openCreateWorkspace}
        >
          Create workspace
        </button>
      </div>
    );
  } else {
    subtitle = `Manage who can work in ${selectedWorkspace.name}.`;
    body = (
      <MembersSection
        key={selectedWorkspace.id}
        workspace={selectedWorkspace}
      />
    );
  }

  const isOwner = selectedWorkspace?.ownerId === user.id;

  return (
    <div className="team-page">
      <div className="team-header">
        <div>
          <h1>Team</h1>
          <p>{subtitle}</p>
        </div>

        {status === "ready" && selectedWorkspace && (
          <div className="team-header-actions">
            <span className="team-role-chip">
              Your role: <strong>{isOwner ? "Owner" : "Editor"}</strong>
            </span>

            {isOwner && (
              <button
                type="button"
                className="team-button primary"
                onClick={() => openAddMember(selectedWorkspace)}
              >
                + Add member
              </button>
            )}
          </div>
        )}
      </div>

      {body}
    </div>
  );
}

export default TeamPage;
