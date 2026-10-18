import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, setUnauthorizedHandler } from "../../lib/apiClient";
import { fetchProfile, loginRequest } from "./authApi";
import { AuthContext } from "./authContext";
import {
  clearAccessToken,
  getAccessToken,
  saveAccessToken,
} from "./authStorage";

/*
 * status:
 *   "loading"       a stored token is being checked against the backend
 *   "authenticated" `user` holds the profile returned by GET /api/users/profile
 *   "anonymous"     no (valid) session
 *   "error"         the token could not be checked (network down, 5xx);
 *                   it is kept so the user can retry instead of being
 *                   logged out by a temporary outage
 */
function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState(() =>
    getAccessToken() ? "loading" : "anonymous"
  );
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  const clearSession = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setError("");
    setStatus("anonymous");
  }, []);

  // Any authenticated request that comes back 401 (expired, tampered or
  // revoked token) ends the session.
  useEffect(() => {
    setUnauthorizedHandler(clearSession);

    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Page refresh: the token survives in sessionStorage, the profile does
  // not, so load it again.
  useEffect(() => {
    if (!getAccessToken()) {
      return undefined;
    }

    let ignore = false;

    fetchProfile()
      .then((profile) => {
        if (!ignore) {
          setUser(profile);
          setStatus("authenticated");
        }
      })
      .catch((err) => {
        // A 401 has already been handled by clearSession.
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

  const login = useCallback(async (email, password) => {
    const token = await loginRequest(email, password);

    saveAccessToken(token);

    try {
      setUser(await fetchProfile());
      setStatus("authenticated");
    } catch (err) {
      // Never leave a token behind that we could not turn into a session.
      clearSession();
      throw err;
    }
  }, [clearSession]);

  const retry = useCallback(() => {
    setError("");
    setStatus("loading");
    setAttempt((previous) => previous + 1);
  }, []);

  const value = useMemo(
    () => ({ user, status, error, login, logout: clearSession, retry }),
    [user, status, error, login, clearSession, retry]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
