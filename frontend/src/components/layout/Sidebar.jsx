
import "./sidebar.css";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "../../features/auth/useAuth";
import { useWorkspace } from "../../features/workspace/useWorkspace";
import {
  ChevronDownIcon,
  CrownIcon,
  DocumentIcon,
  HomeIcon,
  PaletteIcon,
  PlayIcon,
  PlusCircleIcon,
  SettingsIcon,
  UserPlusIcon,
  UsersIcon,
  WorkspaceIcon,
} from "./SidebarIcons";

// Temporary plan data until billing is built.
const plan = {
  name: "Pro Plan",
  creditsLeft: 500,
  creditsTotal: 1000,
};

const navigationItems = [
  { label: "Dashboard", href: "/dashboard", icon: HomeIcon },
  { label: "Create Post", href: "/create", icon: PlusCircleIcon },
  { label: "My Content", href: "/content", icon: DocumentIcon },
  { label: "Brand Kit", href: "/brand-kit", icon: PaletteIcon },
  { label: "Team", href: "/team", icon: UsersIcon },
  { label: "Settings", href: "/settings", icon: SettingsIcon },
];

// An item is active on its own page and on any page nested under it,
// e.g. "/content" and "/content/123" both highlight My Content.
function isActivePath(pathname, href) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Sidebar() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const {
    workspaces,
    status,
    error,
    selectedWorkspace,
    selectWorkspace,
    reload,
    openCreateWorkspace,
    openAddMember,
  } = useWorkspace();
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false);

  const creditsPercent = Math.round(
    (plan.creditsLeft / plan.creditsTotal) * 100
  );

  // What the switcher button shows for each state of the workspace list.
  let switcherName;
  let switcherMeta;

  if (status === "loading") {
    switcherName = "Loading...";
    switcherMeta = "Fetching your workspaces";
  } else if (status === "error") {
    switcherName = "Workspaces unavailable";
    switcherMeta = "Open to try again";
  } else if (!selectedWorkspace) {
    switcherName = "No workspace yet";
    switcherMeta = "Create your first one";
  } else {
    switcherName = selectedWorkspace.name;
    switcherMeta = selectedWorkspace.ownerId === user.id ? "Owner" : "Editor";
  }

  return (
    <aside className="sidebar">
      {/* Brand */}
      <Link to="/" className="sidebar-brand" aria-label="PublishPro-AI home">
        <span className="brand-mark">
          <PlayIcon size={18} />
        </span>
        <span className="brand-name">PublishPro-AI</span>
      </Link>

      {/* Workspace switcher */}
      <button
        type="button"
        className="workspace-switcher"
        aria-label="Switch workspace"
        aria-expanded={isWorkspaceOpen}
        onClick={() => setIsWorkspaceOpen((previous) => !previous)}
      >
        <span className="workspace-avatar">
          <WorkspaceIcon size={20} />
        </span>

        <span className="workspace-text">
          <span className="workspace-name">{switcherName}</span>
          <span className="workspace-meta">{switcherMeta}</span>
        </span>

        <ChevronDownIcon size={18} className="workspace-chevron" />
      </button>

      {/* Workspace dropdown */}
      {isWorkspaceOpen && (
        <div className="workspace-dropdown">
          {status === "error" && (
            <>
              <p className="workspace-dropdown-error" role="alert">
                {error}
              </p>

              <button
                type="button"
                className="workspace-create"
                onClick={reload}
              >
                Try again
              </button>
            </>
          )}

          {status === "ready" && workspaces.length === 0 && (
            <p className="workspace-dropdown-note">
              You don't have a workspace yet.
            </p>
          )}

          {workspaces.length > 0 && (
            <>
              <p className="workspace-dropdown-heading">
                Switch workspace
              </p>

              {workspaces.map((item) => {
                const isSelected = selectedWorkspace?.id === item.id;

                return (
                  <div key={item.id} className="workspace-row">
                    <button
                      type="button"
                      className="workspace-option"
                      aria-pressed={isSelected}
                      onClick={() => {
                        selectWorkspace(item.id);
                        setIsWorkspaceOpen(false);
                      }}
                    >
                      <span className="workspace-avatar">
                        <WorkspaceIcon size={18} />
                      </span>

                      <span className="workspace-option-name">{item.name}</span>

                      {isSelected && (
                        <span className="workspace-option-check" aria-label="Selected">
                          ✓
                        </span>
                      )}
                    </button>

                    {/* Only the owner of a workspace can add members to it. */}
                    {item.ownerId === user.id && (
                      <button
                        type="button"
                        className="workspace-add-member"
                        title="Add member"
                        aria-label={`Add member to ${item.name}`}
                        onClick={() => {
                          setIsWorkspaceOpen(false);
                          openAddMember(item);
                        }}
                      >
                        <UserPlusIcon size={18} />
                      </button>
                    )}
                  </div>
                );
              })}
            </>
          )}

          {status === "ready" && (
            <button
              type="button"
              className="workspace-create"
              onClick={() => {
                setIsWorkspaceOpen(false);
                openCreateWorkspace();
              }}
            >
              + Create workspace
            </button>
          )}
        </div>
      )}

      {/* Main navigation */}
      <nav className="sidebar-nav" aria-label="Main navigation">
        {navigationItems.map(({ label, href, icon: NavIcon }) => {
          const active = isActivePath(pathname, href);

          return (
            <Link
              key={label}
              to={href}
              className={`nav-item${active ? " active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              <NavIcon size={20} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Plan and credits */}
      <section className="plan-card" aria-label="Current plan">
        <div className="plan-header">
          <CrownIcon size={26} className="plan-crown" />

          <div className="plan-text">
            <span className="plan-name">{plan.name}</span>
            <span className="plan-credits">
              {plan.creditsLeft} credits left
            </span>
          </div>
        </div>

        <div
          className="plan-progress"
          role="progressbar"
          aria-label="Credits remaining"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={creditsPercent}
        >
          <div
            className="plan-progress-fill"
            style={{ width: `${creditsPercent}%` }}
          />
        </div>

        <button type="button" className="plan-upgrade">
          Upgrade Plan
        </button>
      </section>
    </aside>
  );
}

export default Sidebar;
