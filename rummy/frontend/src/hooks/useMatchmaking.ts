import { useCallback, useRef, useState } from "react";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "";

export interface MatchmakingCriteria {
  name: string;
  mode: "free" | "real_money";
  entry_fee_paise: number;
  max_players: number;
  num_deals: number;
  pool_limit: number | null;
  turn_seconds?: number;
  starting_chips?: number;
}

type SearchStatus = "idle" | "searching" | "matched" | "no_opponent" | "error";

interface MatchmakingResult {
  status: SearchStatus;
  tableId: string | null;
  solo: boolean;
  errorMessage: string | null;
  elapsedSeconds: number;
  start: (criteria: MatchmakingCriteria) => void;
  cancel: () => void;
  reset: () => void;
}

/** Drives the /ws/matchmaking search: connect, send criteria, wait for a pairing
 * (or the server's own timeout/no-opponent/solo-bot-table fallback), expose a live
 * elapsed-seconds counter for the "Finding Opponent... 00:23" UI. */
export function useMatchmaking(token: string | null): MatchmakingResult {
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [tableId, setTableId] = useState<string | null>(null);
  const [solo, setSolo] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTicking = useCallback(() => {
    if (tickRef.current) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const start = useCallback(
    (criteria: MatchmakingCriteria) => {
      if (!token) return;
      setStatus("searching");
      setTableId(null);
      setSolo(false);
      setErrorMessage(null);
      setElapsedSeconds(0);

      const url = `${WS_BASE}/ws/matchmaking?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify(criteria));
        tickRef.current = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "matched") {
          stopTicking();
          setTableId(msg.table_id);
          setSolo(!!msg.solo);
          setStatus("matched");
        } else if (msg.type === "no_opponent") {
          stopTicking();
          setStatus("no_opponent");
        } else if (msg.type === "cancelled") {
          stopTicking();
          setStatus("idle");
        } else if (msg.type === "error") {
          stopTicking();
          setErrorMessage(msg.message);
          setStatus("error");
        }
      };
      ws.onerror = () => ws.close();
      ws.onclose = () => stopTicking();
    },
    [token, stopTicking]
  );

  const cancel = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: "cancel" }));
  }, []);

  const reset = useCallback(() => {
    stopTicking();
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("idle");
    setTableId(null);
    setSolo(false);
    setErrorMessage(null);
    setElapsedSeconds(0);
  }, [stopTicking]);

  return { status, tableId, solo, errorMessage, elapsedSeconds, start, cancel, reset };
}
