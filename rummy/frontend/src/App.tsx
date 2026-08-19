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
      <div className="min-h-screen flex items-center justify-center text-slate-400">
        {failed ? "Could not reach the game server. Please retry." : "Loading…"}
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
