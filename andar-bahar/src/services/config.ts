import { Preferences } from "@capacitor/preferences";
import type { Card } from "../game/deck";
import type { Side } from "../game/andarBahar";

const KEYS = {
  serverUrl: "server_url",
  balance: "balance",
  clientSeed: "client_seed",
  nonce: "nonce",
  history: "history",
  token: "ab_token",
  tokenAt: "ab_token_at",
  authEmail: "ab_email",
  authPassword: "ab_password",
} as const;

const HISTORY_CAP = 50;

export interface HistoryEntry {
  id: string;
  ts: number;
  openCard: Card;
  bet: Side;
  stake: number;
  winner: Side;
  won: boolean;
  payout: number;
}

const DEFAULT_SERVER_URL = "https://deals-rummy-backend.onrender.com";

export async function getServerUrl(): Promise<string> {
  const { value } = await Preferences.get({ key: KEYS.serverUrl });
  if (value == null) return DEFAULT_SERVER_URL; // never explicitly set — default to online
  return value.trim(); // explicitly set (including cleared to "" via Settings) — respect it
}

export async function setServerUrl(url: string): Promise<void> {
  await Preferences.set({ key: KEYS.serverUrl, value: url.trim() });
}

export async function getBalance(fallback = 1000): Promise<number> {
  const { value } = await Preferences.get({ key: KEYS.balance });
  const n = value == null ? NaN : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export async function setBalance(balance: number): Promise<void> {
  await Preferences.set({ key: KEYS.balance, value: String(Math.round(balance)) });
}

export async function getClientSeed(): Promise<string> {
  const { value } = await Preferences.get({ key: KEYS.clientSeed });
  if (value) return value;
  const seed = Math.random().toString(36).slice(2) + Date.now().toString(36);
  await Preferences.set({ key: KEYS.clientSeed, value: seed });
  return seed;
}

export async function nextNonce(): Promise<number> {
  const { value } = await Preferences.get({ key: KEYS.nonce });
  const n = (value ? Number(value) : 0) + 1;
  await Preferences.set({ key: KEYS.nonce, value: String(n) });
  return n;
}

export async function getHistory(): Promise<HistoryEntry[]> {
  const { value } = await Preferences.get({ key: KEYS.history });
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function pushHistory(entry: HistoryEntry): Promise<HistoryEntry[]> {
  const current = await getHistory();
  const next = [entry, ...current].slice(0, HISTORY_CAP);
  await Preferences.set({ key: KEYS.history, value: JSON.stringify(next) });
  return next;
}

// ---- guest auth (persisted so re-launching the app reuses the same account) ----

export interface AuthState {
  token: string | null;
  tokenAt: number;
  email: string | null;
  password: string | null;
}

export async function getAuthState(): Promise<AuthState> {
  const [token, tokenAt, email, password] = await Promise.all([
    Preferences.get({ key: KEYS.token }).then((r) => r.value),
    Preferences.get({ key: KEYS.tokenAt }).then((r) => Number(r.value) || 0),
    Preferences.get({ key: KEYS.authEmail }).then((r) => r.value),
    Preferences.get({ key: KEYS.authPassword }).then((r) => r.value),
  ]);
  return { token, tokenAt, email, password };
}

export async function saveAuthState(state: AuthState): Promise<void> {
  await Promise.all([
    Preferences.set({ key: KEYS.token, value: state.token ?? "" }),
    Preferences.set({ key: KEYS.tokenAt, value: String(state.tokenAt) }),
    Preferences.set({ key: KEYS.authEmail, value: state.email ?? "" }),
    Preferences.set({ key: KEYS.authPassword, value: state.password ?? "" }),
  ]);
}
