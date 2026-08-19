import axios from "axios";
import { AuthApi } from "./api";

// Temporary stand-in until main-website owns real login/register: each browser gets
// its own persistent guest account (stored in localStorage) instead of everyone
// sharing one login — otherwise two guests could never sit at the same table.
const GUEST_ID_KEY = "rummy_guest_id";

function getOrCreateGuestId(): string {
  let id = localStorage.getItem(GUEST_ID_KEY);
  if (!id) {
    id = Math.random().toString(36).slice(2, 10);
    localStorage.setItem(GUEST_ID_KEY, id);
  }
  return id;
}

async function bootstrap(): Promise<{ access_token: string; username: string }> {
  const id = getOrCreateGuestId();
  const email = `guest-${id}@rummy-guest.app`;
  const username = `Guest${id.slice(0, 4)}`;
  const password = `Guest-${id}-Aa1!`;

  try {
    const { access_token } = await AuthApi.login(email, password);
    return { access_token, username };
  } catch {
    // First visit from this browser — the guest account doesn't exist yet.
    try {
      await AuthApi.register(email, username, password, true);
    } catch (err) {
      // Another concurrent bootstrap (e.g. a second browser tab, or a dev-mode
      // double-effect firing) may have already registered this exact guest
      // between our login attempt and this one — that's fine, fall through to
      // login. Any other failure should still surface.
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (status !== 409) throw err;
    }
    const { access_token } = await AuthApi.login(email, password);
    return { access_token, username };
  }
}

// Dedupe concurrent callers (React 18 StrictMode double-invokes effects in dev,
// which would otherwise fire two independent login-or-register races) onto a
// single in-flight bootstrap.
let inFlight: Promise<{ access_token: string; username: string }> | null = null;

export function ensureGuestSession(): Promise<{ access_token: string; username: string }> {
  if (!inFlight) {
    inFlight = bootstrap().finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}
