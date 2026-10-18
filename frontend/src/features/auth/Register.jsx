import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { registerRequest } from "./authApi";
import AuthLayout from "./AuthLayout";
import { useAuth } from "./useAuth";

// Mirrors RegisterRequest on the backend (@Size(min = 8) on the password).
const MIN_PASSWORD_LENGTH = 8;

function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const { status, login } = useAuth();
  const location = useLocation();

  async function handleSubmit(event) {
    event.preventDefault();

    const cleanName = name.trim();
    const cleanEmail = email.trim();

    if (!cleanName) {
      setError("Name is required.");
      return;
    }

    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(
        `Password must contain at least ${MIN_PASSWORD_LENGTH} characters.`
      );
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      await registerRequest(cleanName, cleanEmail, password);
    } catch (err) {
      // e.g. 409 "Email is already registered"
      setError(err.message || "Sign up failed. Please try again.");
      setIsLoading(false);
      return;
    }

    try {
      // The account exists now; log straight in. When this resolves the
      // provider is "authenticated" and the redirect below takes over.
      await login(cleanEmail, password);
    } catch {
      setError(
        "Your account was created, but we couldn't log you in. " +
          "Please log in with your new details."
      );
      setIsLoading(false);
    }
  }

  // Already logged in (or just signed up): go where the user was heading.
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
      title="Create your account."
      subtitle="Start turning your video ideas into content that stands out."
    >
      <form className="login-form" onSubmit={handleSubmit}>
        <label htmlFor="name">Full name</label>
        <input
          id="name"
          name="name"
          type="text"
          placeholder="Your name"
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />

        <label htmlFor="email">Email address</label>
        <input
          id="email"
          name="email"
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
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
          placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
          autoComplete="new-password"
          minLength={MIN_PASSWORD_LENGTH}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="login-submit"
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? "Creating account..." : "Create account"}
          <span aria-hidden="true">→</span>
        </button>
      </form>

      <p className="login-switch">
        Already have an account?{" "}
        <Link to="/login" state={location.state}>
          Log in
        </Link>
      </p>

      <p className="login-footer">
        Create, polish, and publish with confidence.
      </p>
    </AuthLayout>
  );
}

export default Register;
