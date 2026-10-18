// The JWT lives in sessionStorage under "accessToken" (the key the login
// form already used). It survives a page refresh but is dropped when the
// tab closes. Like any browser storage it is readable by scripts on this
// origin, so the app must never render untrusted HTML.
const TOKEN_KEY = "accessToken";

// Written by an earlier version of the login form; removed so a stale copy
// of the user's details is not left behind.
const LEGACY_USER_KEY = "authUser";

export function getAccessToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveAccessToken(token) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(LEGACY_USER_KEY);
  } catch {
    // Storage unavailable: there is nothing to clear.
  }
}
