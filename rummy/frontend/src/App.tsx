import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import Lobby from "./pages/Lobby";
import GameTable from "./pages/GameTable";
import Wallet from "./pages/Wallet";
import { useAuth } from "./store/auth";
import { ensureGuestSession } from "./services/guestAuth";

// Forces a full remount when navigating from one table to another (e.g. Play Again),
// so all per-table component state (hand groups, dismissed-result flags, etc.) starts fresh
// instead of trying to reconcile onto the new table's data in place.
function GameTableRoute() {
  const { tableId } = useParams();
  return <GameTable key={tableId} />;
}

export default function App() {
  const token = useAuth((s) => s.token);
  const setAuth = useAuth((s) => s.setAuth);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (token) return;
    ensureGuestSession()
      .then(({ access_token, username }) => setAuth(access_token, username))
      .catch(() => setFailed(true));
  }, [token, setAuth]);

  if (!token) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center gap-5"
        style={{ background: "radial-gradient(circle at 50% 40%, #143a29 0%, #0f2a1e 45%, #0b1f17 100%)" }}
      >
        <div
          className="w-24 h-24 rounded-3xl border-4 border-gold-500 flex items-center justify-center shadow-glow"
          style={{ background: "linear-gradient(160deg, #1f2733, #0a0c10)" }}
        >
          <span className="text-5xl text-gold-500" style={{ textShadow: "0 4px 12px rgba(0,0,0,0.6)" }}>
            ♠
          </span>
        </div>
        <div className="font-display text-2xl font-bold text-gold-500 tracking-wide">Rummy</div>
        {failed ? (
          <p className="text-red-400 text-sm">Could not reach the game server. Please retry.</p>
        ) : (
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <span className="w-2 h-2 rounded-full bg-gold-500 animate-pulse" />
            <span>Loading…</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/" element={<Navigate to="/lobby" replace />} />
      <Route path="/lobby" element={<Lobby />} />
      <Route path="/wallet" element={<Wallet />} />
      <Route path="/table/:tableId" element={<GameTableRoute />} />
      <Route path="*" element={<Navigate to="/lobby" replace />} />
    </Routes>
  );
}
