import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ClientAction,
  ServerMessage,
  TableState,
} from "../services/gameTypes";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "";

/**
 * Connects to the game WebSocket for a table and exposes the live table state,
 * this player's private hand, and a `send` function for intents. Automatically
 * reconnects with backoff so a dropped connection re-seats the player.
 */
export function useGameSocket(tableId: string, token: string | null) {
  const [state, setState] = useState<TableState | null>(null);
  const [hand, setHand] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const closedRef = useRef(false);

  const connect = useCallback(() => {
    if (!token) return;
    const url = `${WS_BASE}/ws/game/${tableId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retryRef.current = 0;
      ws.send(JSON.stringify({ action: "sync" } as ClientAction));
    };
    ws.onmessage = (ev) => {
      const msg: ServerMessage = JSON.parse(ev.data);
      if (msg.type === "state") setState(msg.state);
      else if (msg.type === "hand") setHand(msg.cards);
      else if (msg.type === "error") setLastError(msg.message);
    };
    ws.onclose = () => {
      setConnected(false);
      if (closedRef.current) return;
      const delay = Math.min(1000 * 2 ** retryRef.current, 8000);
      retryRef.current += 1;
      setTimeout(connect, delay);
    };
    ws.onerror = () => ws.close();
  }, [tableId, token]);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => {
      closedRef.current = true;
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((action: ClientAction) => {
    // A fresh id per intent so the server can no-op an accidental duplicate (double
    // click, a retry after a dropped ack) instead of applying the action twice.
    const action_id = action.action === "sync" ? undefined : crypto.randomUUID();
    wsRef.current?.send(JSON.stringify({ ...action, action_id }));
  }, []);

  return { state, hand, connected, lastError, send };
}
