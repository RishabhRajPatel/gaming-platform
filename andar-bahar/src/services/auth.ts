import { getAuthState, saveAuthState, type AuthState } from "./config";

// Guest auth, same pattern as the Teen Patti web app's ensureAuth(): register a
// throwaway guest account on first launch, then reuse its token across sessions.
function randId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function ensureGuestCreds(state: AuthState): AuthState {
  if (state.email && state.password) return state;
  const id = randId();
  return {
    ...state,
    email: `guest-${id}@andarbahar-guest.com`,
    password: `g${randId()}${randId()}`,
  };
}

export async function apiFetch(serverUrl: string, path: string, opts: RequestInit = {}): Promise<Response> {
  const state = await getAuthState();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  return fetch(`${serverUrl.replace(/\/$/, "")}${path}`, { ...opts, headers });
}

async function login(serverUrl: string, state: AuthState): Promise<AuthState | null> {
  const res = await fetch(`${serverUrl.replace(/\/$/, "")}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: state.email, password: state.password }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return { ...state, token: data.access_token, tokenAt: Date.now() };
}

export let lastAuthError: string | null = null;

async function ensureAuthUncached(serverUrl: string): Promise<boolean> {
  lastAuthError = null;
  if (!serverUrl.trim()) {
    lastAuthError = "No server URL configured.";
    return false;
  }
  try {
    let state = ensureGuestCreds(await getAuthState());
    await saveAuthState(state); // persist generated guest creds immediately, before any await races a concurrent caller
    if (state.token && Date.now() - state.tokenAt < 50 * 60 * 1000) {
      return true;
    }
    const loggedIn = await login(serverUrl, state);
    if (loggedIn) {
      await saveAuthState(loggedIn);
      return true;
    }
    const reg = await fetch(`${serverUrl.replace(/\/$/, "")}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: state.email,
        username: `guest${randId()}`,
        password: state.password,
        is_18_plus: false,
      }),
    });
    if (!reg.ok && reg.status !== 409) {
      const body = await reg.json().catch(() => null);
      lastAuthError = `Registration failed: ${body?.detail ?? reg.status}`;
      return false;
    }
    const relogged = await login(serverUrl, state);
    if (!relogged) {
      lastAuthError = "Registered, but the follow-up login failed.";
      return false;
    }
    await saveAuthState(relogged);
    return true;
  } catch (err) {
    // Network/CORS failures throw instead of resolving to a non-ok response —
    // catch them here so callers always get a clean true/false, never a
    // rejected promise, and can show *why* it failed.
    lastAuthError = err instanceof Error ? err.message : "Network error.";
    return false;
  }
}

let inFlight: Promise<boolean> | null = null;

/**
 * Ensures a valid, persisted guest session exists — registers one if needed.
 * Concurrent callers (e.g. React StrictMode double-invoking an effect) share
 * a single in-flight attempt instead of racing two separate registrations.
 */
export function ensureAuth(serverUrl: string): Promise<boolean> {
  if (!inFlight) {
    inFlight = ensureAuthUncached(serverUrl).finally(() => { inFlight = null; });
  }
  return inFlight;
}
