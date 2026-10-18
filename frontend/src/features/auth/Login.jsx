import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import AuthLayout from "./AuthLayout";
import { useAuth } from "./useAuth";

function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const { status, login } = useAuth();
  const location = useLocation();

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setIsLoading(true);

    try {
      // Logs in, then loads GET /api/users/profile. When it resolves the
      // provider is "authenticated" and the redirect below takes over.
      await login(username.trim(), password);
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  // Already logged in (or just logged in): go where the user was heading.
  if (status === "authenticated") {
    const from = location.state?.from;

    return (
      <Navigate
        to={from ? `${from.pathname}${from.search}` : "/dashboard"}
        replace
      />
    );
  }

  return (
    <AuthLayout
      title="Welcome back."
      subtitle="Your next great video starts here."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <label htmlFor="username">Email address</label>
        <input
          id="username"
          name="username"
          type="email"
          placeholder="you@example.com"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          required
        />

        <div className="password-label-row">
          <label htmlFor="password">Password</label>
          <button
            type="button"
            className="password-toggle"
            onClick={() => setShowPassword((previous) => !previous)}
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>

        <input
          id="password"
          name="password"
          type={showPassword ? "text" : "password"}
          placeholder="Enter your password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <div className="forgot-password-row">
          <button
            type="button"
            className="forgot-password"
            onClick={() => {
              // Password recovery will be implemented separately.
            }}
          >
            Forgot password?
          </button>
        </div>

        <button
          type="submit"
          className="login-submit"
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? "Logging in..." : "Log in"}
          <span aria-hidden="true">→</span>
        </button>
      </form>

      <p className="login-switch">
        New to PublishPro-AI?{" "}
        {/* Keep `from` so the user still lands on the page they wanted. */}
        <Link to="/register" state={location.state}>
          Create an account
        </Link>
      </p>

      <p className="login-footer">
        Create, polish, and publish with confidence.
      </p>
    </AuthLayout>
  );
}

export default Login;
