import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../features/auth/useAuth";
import "./auth-gate.css";

// Wraps every page that needs a logged-in user.
function ProtectedRoute() {
  const { status, error, retry, logout } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="auth-gate" role="status">
        <p>Loading your account...</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="auth-gate" role="alert">
        <h1>We couldn't load your account</h1>
        <p>{error}</p>

        <div className="auth-gate-actions">
          <button type="button" onClick={retry}>
            Try again
          </button>
          <button type="button" className="secondary" onClick={logout}>
            Back to login
          </button>
        </div>
      </div>
    );
  }

  if (status !== "authenticated") {
    // Remember where the user was heading so login can send them back.
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export default ProtectedRoute;
