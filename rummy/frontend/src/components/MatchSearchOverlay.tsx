import { useEffect, useState } from "react";

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  status: "searching" | "matched" | "no_opponent" | "error";
  elapsedSeconds: number;
  solo: boolean;
  errorMessage: string | null;
  onCancel: () => void;
  onTryAgain: () => void;
  onBackToLobby: () => void;
  onCountdownDone: () => void;
}

/** Full-screen matchmaking overlay: searching → match-found countdown → (or)
 * no-opponent dead end. Purely presentational — `useMatchmaking` drives the state. */
export default function MatchSearchOverlay({
  status, elapsedSeconds, solo, errorMessage, onCancel, onTryAgain, onBackToLobby, onCountdownDone,
}: Props) {
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    if (status !== "matched") return;
    if (countdown <= 0) {
      onCountdownDone();
      return;
    }
    const t = setTimeout(() => setCountdown((c) => c - 1), 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, countdown]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="card-surface w-full max-w-sm p-8 text-center">
        {status === "searching" && (
          <>
            <h2 className="font-display text-xl font-bold text-gold-400 mb-1">Deals Rummy</h2>
            <p className="text-slate-300 mb-6">Finding Opponent…</p>
            <div className="flex items-center justify-center gap-2 mb-6">
              <span className="w-2 h-2 rounded-full bg-gold-500 animate-pulse" />
              <span className="font-mono text-3xl text-slate-100">{fmt(elapsedSeconds)}</span>
            </div>
            <p className="text-xs text-slate-500 mb-6">
              Looking for a player with the same table settings…
            </p>
            <button className="btn-ghost rounded-full px-6 py-2 w-full" onClick={onCancel}>
              Cancel Match
            </button>
          </>
        )}

        {status === "matched" && (
          <>
            <h2 className="font-display text-xl font-bold text-green-400 mb-4">
              {solo ? "Table Ready" : "Match Found! 🎉"}
            </h2>
            {!solo && <p className="text-slate-300 mb-2">Opponent found — get ready</p>}
            {solo && (
              <p className="text-slate-300 mb-2 text-sm">
                No opponent turned up in time — starting a practice table instead.
              </p>
            )}
            <div className="font-display text-5xl font-bold text-gold-400 my-6">
              {countdown > 0 ? countdown : "GO"}
            </div>
          </>
        )}

        {status === "no_opponent" && (
          <>
            <h2 className="font-display text-xl font-bold text-red-400 mb-2">No Opponent Found</h2>
            <p className="text-slate-400 text-sm mb-6">
              Nobody with the same entry amount was searching. Your entry fee was never
              charged — nothing to refund.
            </p>
            <div className="flex gap-3">
              <button className="btn-ghost rounded-full px-4 py-2 flex-1" onClick={onBackToLobby}>
                Back to Lobby
              </button>
              <button className="btn-gold rounded-full px-4 py-2 flex-1" onClick={onTryAgain}>
                Try Again
              </button>
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <h2 className="font-display text-xl font-bold text-red-400 mb-2">Couldn't Search</h2>
            <p className="text-slate-400 text-sm mb-6">{errorMessage ?? "Something went wrong."}</p>
            <button className="btn-gold rounded-full px-4 py-2 w-full" onClick={onBackToLobby}>
              Back to Lobby
            </button>
          </>
        )}
      </div>
    </div>
  );
}
