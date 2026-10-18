import { getAccessToken } from "../features/auth/authStorage";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

// status 0 means the request never got an HTTP response (network/CORS).
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// AuthProvider registers a callback here so that a 401 on any
// authenticated request ends the session in one place.
let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

// The backend returns JSON for some errors and plain text for others
// (e.g. "Invalid email or password"), so read the body as text first.
async function readBody(response) {
  const text = await response.text();

  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function messageFor(status, data) {
  // Only trust the server's wording for client errors; a 5xx body can be
  // a stack trace or a proxy's HTML page.
  if (status < 500) {
    if (typeof data === "string" && data.length <= 200) {
      return data;
    }

    if (typeof data?.message === "string") {
      return data.message;
    }
  }

  if (status === 401) {
    return "Your session has expired. Please log in again.";
  }

  if (status === 403) {
    return "You don't have permission to do that.";
  }

  if (status >= 500) {
    return "Something went wrong on our side. Please try again.";
  }

  return "The request could not be completed.";
}

/**
 * Calls the backend and returns the parsed JSON body.
 *
 * @param {string} path  e.g. "/api/users/profile"
 * @param {{ method?: string, body?: unknown, auth?: boolean }} options
 *   auth: true sends the stored JWT as "Authorization: Bearer <token>".
 */
export async function apiRequest(
  path,
  { method = "GET", body, auth = false } = {}
) {
  const headers = {};

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getAccessToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      "Unable to connect to the server. Check that the backend is running.",
      0
    );
  }

  const data = await readBody(response);

  if (!response.ok) {
    if (response.status === 401 && auth && unauthorizedHandler) {
      unauthorizedHandler();
    }

    throw new ApiError(messageFor(response.status, data), response.status);
  }

  return data;
}
