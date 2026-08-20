import type { Card } from "../game/deck";
import type { Side } from "../game/andarBahar";
import { getAuthState } from "./config";

export interface TableBet {
  user_id: string;
  name: string;
  side: Side;
  stake: number;
}

export interface TableRound {
  middle: Card;
  steps: { side: Side; card: Card }[];
  andar: Card[];
  bahar: Card[];
  winner: Side;
  cardsDealt: number;
}

export interface TablePublicState {
  table_id: string;
  phase: "waiting" | "betting" | "dealing" | "settled";
  round_number: number;
  betting_seconds: number;
  bets: TableBet[];
  round: TableRound | null;
  settlements: Record<string, { payout: number; won: boolean; returned: number }>;
}

export interface AndarBaharSocketHandlers {
  onState?: (state: TablePublicState) => void;
  onEvent?: (event: string, payload: Record<string, unknown>) => void;
  onError?: (message: string) => void;
  onClose?: () => void;
}

export interface AndarBaharSocket {
  bet(side: Side, stake: number): void;
  close(): void;
}

function randActionId(): string {
  return Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
}

/** Connects to the real-time shared-outcome table (app/websocket/andar_bahar_ws.py). */
export async function connectAndarBaharTable(
  serverUrl: string,
  tableId: string,
  handlers: AndarBaharSocketHandlers,
): Promise<AndarBaharSocket> {
  const { token } = await getAuthState();
  const wsBase = serverUrl.replace(/^http/, "ws");
  const sock = new WebSocket(`${wsBase}/ws/andar-bahar/${tableId}?token=${encodeURIComponent(token ?? "")}`);

  sock.onmessage = (ev) => {
    try {
      const m = JSON.parse(ev.data);
      if (m.type === "state") handlers.onState?.(m.state);
      else if (m.type === "event") handlers.onEvent?.(m.event, m);
      else if (m.type === "error") handlers.onError?.(m.message);
    } catch {
      // ignore malformed frames
    }
  };
  sock.onclose = () => handlers.onClose?.();

  await new Promise<void>((resolve, reject) => {
    sock.onopen = () => resolve();
    sock.onerror = () => reject(new Error("socket failed to open"));
  });

  return {
    bet(side, stake) {
      if (sock.readyState !== WebSocket.OPEN) return;
      sock.send(JSON.stringify({ action: "bet", side, stake, action_id: randActionId() }));
    },
    close() {
      try {
        sock.close();
      } catch {
        // already closed
      }
    },
  };
}
