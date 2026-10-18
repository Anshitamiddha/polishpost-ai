import { apiRequest } from "../../lib/apiClient";

// POST /api/auth/login -> AuthResponse { accessToken, tokenType, user }
export async function loginRequest(email, password) {
  const data = await apiRequest("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });

  if (!data?.accessToken) {
    throw new Error("The server did not return an access token.");
  }

  return data.accessToken;
}

// POST /api/auth/register -> 201 UserResponse { id, name, email }
// (409 "Email is already registered" if the email is taken). It returns no
// token, so the caller logs in afterwards.
export function registerRequest(name, email, password) {
  return apiRequest("/api/auth/register", {
    method: "POST",
    body: { name, email, password },
  });
}

// GET /api/users/profile -> UserResponse { id, name, email }
export function fetchProfile() {
  return apiRequest("/api/users/profile", { auth: true });
}
