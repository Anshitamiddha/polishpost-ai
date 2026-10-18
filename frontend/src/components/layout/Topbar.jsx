import { useAuth } from "../../features/auth/useAuth";
import { getInitials } from "../../lib/getInitials";
import "./topbar.css";

function Topbar() {
  const { user, logout } = useAuth();

  return (
    <header className="topbar">
      <div className="topbar-search">
        <input
          type="search"
          placeholder="Search your content..."
          aria-label="Search your content"
        />
      </div>

      <div className="topbar-actions">
        <button type="button" aria-label="Notifications">
          Notifications
        </button>

        <button
          type="button"
          className="topbar-profile"
          aria-label="Open profile menu"
        >
          <span className="topbar-avatar" aria-hidden="true">
            {getInitials(user?.name)}
          </span>
          <span className="topbar-profile-name">{user?.name}</span>
        </button>

        <button type="button" onClick={logout}>
          Log out
        </button>
      </div>
    </header>
  );
}

export default Topbar;
