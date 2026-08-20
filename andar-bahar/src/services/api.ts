import type { RoundResult, Settlement, Side } from "../game/andarBahar";
import { apiFetch } from "./auth";

export interface Wallet {
  virtual_chips: number;
  real_paise: number;
  bonus_paise: number;
}

export interface TableOut {
  id: string;
  name: string;
  mode: "virtual" | "real";
  status: string;
  max_players: number;
  betting_seconds: number;
  online_players: number;
  is_private: boolean;
  join_code: string | null;
}

export async function getWallet(serverUrl: string): Promise<Wallet | null> {
  const res = await apiFetch(serverUrl, "/api/v1/wallet");
  if (!res.ok) return null;
  return (await res.json()) as Wallet;
}

export async function listTables(serverUrl: string): Promise<TableOut[]> {
  const res = await apiFetch(serverUrl, "/api/v1/andar-bahar/tables");
  if (!res.ok) return [];
  return (await res.json()) as TableOut[];
}

export async function findOrCreateTable(
  serverUrl: string,
  mode: "virtual" | "real",
  bettingSeconds: number,
): Promise<TableOut> {
  const open = (await listTables(serverUrl)).find(
    (t) => t.mode === mode && t.betting_seconds === bettingSeconds && t.online_players < t.max_players,
  );
  if (open) return open;
  const res = await apiFetch(serverUrl, "/api/v1/andar-bahar/tables", {
    method: "POST",
    body: JSON.stringify({ name: "Andar Bahar", mode, max_players: 8, betting_seconds: bettingSeconds }),
  });
  if (!res.ok) throw new Error("could not create table");
  return (await res.json()) as TableOut;
}

export interface DepositOrder {
  deposit_id: string;
  razorpay_order_id: string;
  razorpay_key_id: string;
  amount_paise: number;
  currency: string;
}

/** Same Razorpay flow as Rummy's Wallet page / Teen Patti's addCashOnline(). */
export async function createDepositOrder(serverUrl: string, amountPaise: number): Promise<DepositOrder> {
  const res = await apiFetch(serverUrl, "/api/v1/payments/deposit", {
    method: "POST",
    body: JSON.stringify({ amount_paise: amountPaise }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body?.detail || "Could not start the payment.");
  return body as DepositOrder;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export interface BetResponse {
  round: RoundResult;
  settlement: Settlement;
  balance: number;
  serverSeedHash?: string;
  serverSeed?: string;
}

/**
 * Place a bet against a configured backend. The server is authoritative: it shuffles,
 * runs the round and settles the wallet, returning the full result for the client to
 * animate. Returns null on any failure so the caller can fall back to offline play.
 *
 * Expected endpoint (implement server-side): POST {serverUrl}/api/v1/andar-bahar/bet
 *   body: { bet, stake, client_seed, nonce, token? }
 *   200:  { round, settlement, balance, server_seed_hash, server_seed }
 */
export async function placeBetRemote(
  serverUrl: string,
  body: { bet: Side; stake: number; clientSeed: string; nonce: number; token?: string },
): Promise<BetResponse | null> {
  try {
    const res = await fetch(`${serverUrl.replace(/\/$/, "")}/api/v1/andar-bahar/bet`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(body.token ? { Authorization: `Bearer ${body.token}` } : {}),
      },
      body: JSON.stringify({
        bet: body.bet,
        stake: body.stake,
        client_seed: body.clientSeed,
        nonce: body.nonce,
      }),
    });
    if (!res.ok) return null;
    return (await res.json()) as BetResponse;
  } catch {
    return null;
  }
}

export async function pingServer(serverUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${serverUrl.replace(/\/$/, "")}/api/v1/health`);
    return res.ok;
  } catch {
    return false;
  }
}
