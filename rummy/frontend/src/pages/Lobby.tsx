import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InstallPWAButton from "../components/InstallPWAButton";
import MatchSearchOverlay from "../components/MatchSearchOverlay";
import { useMatchmaking } from "../hooks/useMatchmaking";
import { TableApi, WalletApi, type Wallet } from "../services/api";
import { useAuth } from "../store/auth";

type Mode = "free" | "real_money" | "pool";
type PlayerFilter = "all" | 2 | 4;
type PoolLimit = 101 | 201;
type EntryAmount = 10 | 50 | 100;

const GAMES = [
  { key: "rummy", label: "Rummy", icon: "🃏", enabled: true },
  { key: "teen-patti", label: "Teen Patti", icon: "🂡", enabled: false },
  { key: "ludo", label: "Ludo", icon: "🎲", enabled: false },
  { key: "andar-bahar", label: "Andar & Bahar", icon: "🎴", enabled: false },
];

const ENTRY_AMOUNTS: EntryAmount[] = [10, 50, 100];

export default function Lobby() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [mode, setMode] = useState<Mode>("free");
  const [poolLimit, setPoolLimit] = useState<PoolLimit>(101);
  const [playerFilter, setPlayerFilter] = useState<PlayerFilter>("all");
  const [entryAmount, setEntryAmount] = useState<EntryAmount>(10);
  const [creatingPrivate, setCreatingPrivate] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [joinError, setJoinError] = useState<string | null>(null);
  const username = useAuth((s) => s.username);
  const token = useAuth((s) => s.token);
  const navigate = useNavigate();
  const search = useMatchmaking(token);
  const searchStatus = search.status;

  useEffect(() => {
    WalletApi.get().then(setWallet).catch(() => setWallet(null));
  }, []);

  const tableName = useMemo(() => {
    const names: Record<Mode, string> = {
      free: "Practice Rummy",
      real_money: "Points Rummy",
      pool: `Pool ${poolLimit} Rummy`,
    };
    return names[mode];
  }, [mode, poolLimit]);

  function playNow() {
    search.start({
      name: tableName,
      // Pool Rummy is played for points under the hood — pool_limit is what
      // actually switches the engine into open-ended elimination play.
      mode: mode === "pool" ? "real_money" : mode,
      max_players: playerFilter === "all" ? 2 : playerFilter,
      num_deals: 2,
      entry_fee_paise: mode === "free" ? 0 : entryAmount * 100,
      pool_limit: mode === "pool" ? poolLimit : null,
    });
  }

  async function createPrivateTable() {
    setCreatingPrivate(true);
    try {
      const table = await TableApi.create({
        name: tableName,
        mode: mode === "pool" ? "real_money" : mode,
        max_players: playerFilter === "all" ? 2 : playerFilter,
        num_deals: 2,
        entry_fee_paise: mode === "free" ? 0 : entryAmount * 100,
        pool_limit: mode === "pool" ? poolLimit : null,
        is_private: true,
      });
      if (table.join_code) {
        alert(`Private table created. Share this code to invite others: ${table.join_code}`);
      }
      navigate(`/table/${table.id}`);
    } finally {
      setCreatingPrivate(false);
    }
  }

  async function joinByCode() {
    setJoinError(null);
    const code = joinCode.trim().toUpperCase();
    if (!code) return;
    try {
      const table = await TableApi.getByCode(code);
      navigate(`/table/${table.id}`);
    } catch {
      setJoinError("No table found with that code.");
    }
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h1 className="text-2xl font-display font-bold text-gold-500 tracking-wide">
          🃏 Deals Rummy
        </h1>
        <div className="flex items-center gap-2 text-sm">
          {wallet && (
            <button
              className="card-surface px-3 py-1.5 text-gold-400 font-medium flex items-center gap-2 hover:bg-ink-800/60"
              onClick={() => navigate("/wallet")}
            >
              <span>💰 ₹{(wallet.real_paise / 100).toFixed(2)}</span>
              <span className="text-slate-500">|</span>
              <span>🪙 {wallet.virtual_chips}</span>
            </button>
          )}
          <button className="btn-gold px-3 py-1.5 rounded-full" onClick={() => navigate("/wallet")}>
            + Add
          </button>
          <button className="btn-ghost px-3 py-1.5 rounded-full" onClick={() => navigate("/wallet")}>
            ↓ Withdraw
          </button>
          <InstallPWAButton />
          <div className="flex items-center gap-1.5 pl-2">
            <span className="w-7 h-7 rounded-full bg-gradient-to-br from-ink-700 to-ink-900 border border-gold-500 flex items-center justify-center text-[10px] font-bold">
              {(username ?? "?").slice(0, 2).toUpperCase()}
            </span>
            <span className="text-slate-300">{username}</span>
          </div>
        </div>
      </header>

      <div className="flex flex-col sm:flex-row gap-4">
        {/* Game picker — only Rummy is live, the rest are placeholders for future games */}
        <nav className="flex sm:flex-col gap-2 sm:w-32 shrink-0">
          {GAMES.map((g) => (
            <div
              key={g.key}
              className={`card-surface px-3 py-3 text-center text-xs font-medium transition-transform ${
                g.enabled
                  ? "ring-2 ring-gold-500 text-gold-400 shadow-glow"
                  : "opacity-40 cursor-not-allowed grayscale"
              }`}
              title={g.enabled ? undefined : "Coming soon"}
            >
              <div className="text-2xl mb-1">{g.icon}</div>
              {g.label}
              {!g.enabled && <div className="text-[10px] text-slate-500 mt-0.5">Coming soon</div>}
            </div>
          ))}
        </nav>

        <div className="flex-1">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex rounded-full overflow-hidden border border-ink-700">
                {(["real_money", "free", "pool"] as Mode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`px-4 py-2 text-sm font-semibold transition-colors ${
                      mode === m ? "bg-gold-500 text-ink-950" : "bg-ink-800 text-slate-300 hover:bg-ink-700"
                    }`}
                  >
                    {m === "real_money" ? "💰 Points" : m === "free" ? "🎮 Practice" : "🏊 Pool"}
                  </button>
                ))}
              </div>
              {mode === "pool" && (
                <div className="flex rounded-full overflow-hidden border border-ink-700 text-xs">
                  {([101, 201] as PoolLimit[]).map((limit) => (
                    <button
                      key={limit}
                      onClick={() => setPoolLimit(limit)}
                      className={`px-3 py-1.5 font-semibold transition-colors ${
                        poolLimit === limit ? "bg-gold-500 text-ink-950" : "bg-ink-800 text-slate-300 hover:bg-ink-700"
                      }`}
                    >
                      {limit} pts
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-300">
              {(["all", 2, 4] as PlayerFilter[]).map((f) => (
                <label key={f} className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    checked={playerFilter === f}
                    onChange={() => setPlayerFilter(f)}
                    className="accent-gold-500"
                  />
                  {f === "all" ? "All" : `${f} Player`}
                </label>
              ))}
            </div>
          </div>

          {mode !== "free" && (
            <div className="flex items-center gap-3 mb-4">
              <span className="text-sm text-slate-400">Select Entry Amount</span>
              <div className="flex rounded-full overflow-hidden border border-ink-700 text-sm">
                {ENTRY_AMOUNTS.map((amt) => (
                  <button
                    key={amt}
                    onClick={() => setEntryAmount(amt)}
                    className={`px-4 py-1.5 font-semibold transition-colors ${
                      entryAmount === amt ? "bg-gold-500 text-ink-950" : "bg-ink-800 text-slate-300 hover:bg-ink-700"
                    }`}
                  >
                    ₹{amt}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="card-surface p-8 text-center mb-4">
            <p className="text-slate-400 text-sm mb-4">
              {mode === "free"
                ? "Practice for free — no real opponent? A bot fills in shortly."
                : `Matches players searching for the same ${mode === "pool" ? "pool limit" : "entry amount"} and table size.`}
            </p>
            <button className="btn-gold rounded-full px-10 py-3 text-lg font-semibold" onClick={playNow}>
              ▶ Play Now
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3 mb-3 text-sm">
            <button className="btn-ghost px-3 py-1.5 rounded-full" disabled={creatingPrivate} onClick={createPrivateTable}>
              {creatingPrivate ? "Creating…" : "🔒 Create Private Table (invite-only)"}
            </button>
            <div className="flex items-center gap-1.5 ml-auto">
              <input
                className="input py-1 px-2 text-sm w-28 uppercase"
                placeholder="Join code"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                maxLength={6}
              />
              <button className="btn-ghost px-3 py-1" onClick={joinByCode}>
                Join
              </button>
            </div>
          </div>
          {joinError && <p className="text-red-400 text-xs mb-2">{joinError}</p>}
        </div>
      </div>

      {searchStatus !== "idle" && (
        <MatchSearchOverlay
          status={searchStatus}
          elapsedSeconds={search.elapsedSeconds}
          solo={search.solo}
          errorMessage={search.errorMessage}
          onCancel={search.cancel}
          onTryAgain={() => {
            search.reset();
            playNow();
          }}
          onBackToLobby={search.reset}
          onCountdownDone={() => {
            if (search.tableId) navigate(`/table/${search.tableId}`);
          }}
        />
      )}
    </div>
  );
}
