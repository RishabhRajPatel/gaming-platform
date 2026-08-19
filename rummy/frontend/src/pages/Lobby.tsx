import { Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import InstallPWAButton from "../components/InstallPWAButton";
import MatchSearchOverlay from "../components/MatchSearchOverlay";
import { useMatchmaking } from "../hooks/useMatchmaking";
import { TableApi, WalletApi, type Table, type Wallet } from "../services/api";
import { useAuth } from "../store/auth";

type Mode = "free" | "real_money" | "pool";
// Our engine seats 2-4 (see GameConfig.max_players) — the reference lobby's "6 Player"
// filter doesn't map to anything joinable here, so this is 2/4, not 2/6.
type PlayerFilter = "all" | 2 | 4;
type PoolLimit = 101 | 201;

const GAMES = [
  { key: "rummy", label: "Rummy", icon: "🃏", enabled: true },
  { key: "teen-patti", label: "Teen Patti", icon: "🂡", enabled: false },
  { key: "ludo", label: "Ludo", icon: "🎲", enabled: false },
  { key: "andar-bahar", label: "Andar & Bahar", icon: "🎴", enabled: false },
];

// A "tier" is a joinable (stake, table-size) combination, not a literal single table —
// matchmaking spins up a fresh table per match, so tiers never go permanently "full" the
// way one fixed table would. Point values in rupees; min entry mirrors the real risk (our
// scoring caps a losing hand at 80 points — see MAX_HAND_POINTS in scoring.py).
interface Tier {
  id: string;
  pointValue: number | null; // null for Practice (no real stake)
  maxPlayers: 2 | 4;
  poolLimit: PoolLimit | null;
}

const POINT_VALUES = [1, 2, 5, 10];
const MAX_PLAYER_OPTIONS: (2 | 4)[] = [2, 4];

function buildTiers(mode: Mode, poolLimit: PoolLimit): Tier[] {
  if (mode === "free") {
    return MAX_PLAYER_OPTIONS.map((mp) => ({ id: `free-${mp}`, pointValue: null, maxPlayers: mp, poolLimit: null }));
  }
  if (mode === "pool") {
    return MAX_PLAYER_OPTIONS.map((mp) => ({ id: `pool-${poolLimit}-${mp}`, pointValue: 1, maxPlayers: mp, poolLimit }));
  }
  return POINT_VALUES.flatMap((pv) =>
    MAX_PLAYER_OPTIONS.map((mp) => ({ id: `points-${pv}-${mp}`, pointValue: pv, maxPlayers: mp, poolLimit: null }))
  );
}

export default function Lobby() {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [openTables, setOpenTables] = useState<Table[]>([]);
  const [mode, setMode] = useState<Mode>("real_money");
  const [poolLimit, setPoolLimit] = useState<PoolLimit>(101);
  const [playerFilter, setPlayerFilter] = useState<PlayerFilter>("all");
  const [joiningTierId, setJoiningTierId] = useState<string | null>(null);
  const [joinRowError, setJoinRowError] = useState<string | null>(null);
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
    const refresh = () => TableApi.list().then(setOpenTables).catch(() => {});
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, []);

  const tiers = useMemo(
    () => buildTiers(mode, poolLimit).filter((t) => playerFilter === "all" || t.maxPlayers === playerFilter),
    [mode, poolLimit, playerFilter]
  );

  // Real online-player counts, not made-up numbers: sum whoever's actually seated
  // right now across open tables matching this tier's (mode, stake, size, pool limit).
  function getOnlinePlayers(tier: Tier): number {
    const engineMode = mode === "pool" ? "real_money" : mode;
    const entryFeePaise = tier.pointValue == null ? 0 : tier.pointValue * 100;
    return openTables
      .filter(
        (t) =>
          t.mode === engineMode &&
          t.max_players === tier.maxPlayers &&
          t.entry_fee_paise === entryFeePaise &&
          (tier.poolLimit == null ? t.pool_limit == null : t.pool_limit === tier.poolLimit)
      )
      .reduce((sum, t) => sum + t.online_players, 0);
  }

  function tierTableName(tier: Tier): string {
    if (mode === "pool") return `Pool ${tier.poolLimit} Rummy`;
    if (mode === "free") return "Practice Rummy";
    return `Points Rummy ₹${tier.pointValue}`;
  }

  async function joinTier(tier: Tier) {
    setJoinRowError(null);
    setJoiningTierId(tier.id);
    try {
      search.start({
        name: tierTableName(tier),
        mode: mode === "pool" ? "real_money" : mode,
        max_players: tier.maxPlayers,
        num_deals: 2,
        entry_fee_paise: tier.pointValue == null ? 0 : tier.pointValue * 100,
        pool_limit: tier.poolLimit,
      });
    } catch {
      setJoinRowError("Could not join that table right now — try again.");
    } finally {
      setJoiningTierId(null);
    }
  }

  async function createPrivateTable() {
    setCreatingPrivate(true);
    try {
      const table = await TableApi.create({
        name: mode === "pool" ? `Pool ${poolLimit} Rummy` : mode === "free" ? "Practice Rummy" : "Points Rummy",
        mode: mode === "pool" ? "real_money" : mode,
        max_players: playerFilter === "all" ? 2 : playerFilter,
        num_deals: 2,
        entry_fee_paise: mode === "free" ? 0 : POINT_VALUES[0] * 100,
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
    <div className="lobby-casino">
      <div className="max-w-5xl mx-auto p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <button className="lobby-home-btn text-3xl" onClick={() => navigate("/lobby")} title="Home">
          🏠
        </button>
        <div className="flex items-center gap-2 text-sm flex-wrap">
          {wallet && (
            <button
              className="lobby-balance-bar rounded-full px-3 py-1.5 font-bold flex items-center gap-2"
              onClick={() => navigate("/wallet")}
            >
              <span style={{ color: "var(--lobby-gold)" }}>🪙</span>
              <span>₹{(wallet.real_paise / 100).toFixed(2)}</span>
            </button>
          )}
          <button className="lobby-btn-add px-4 py-1.5 rounded-full" onClick={() => navigate("/wallet")}>
            ADD
          </button>
          <button className="lobby-btn-withdraw px-4 py-1.5 rounded-full" onClick={() => navigate("/wallet")}>
            WITHDRAW
          </button>
          <InstallPWAButton />
          <div className="flex items-center gap-1.5 pl-2">
            <span className="w-7 h-7 rounded-full bg-gradient-to-br from-ink-700 to-ink-900 border border-gold-500 flex items-center justify-center text-[10px] font-bold">
              {(username ?? "?").slice(0, 2).toUpperCase()}
            </span>
            <span className="text-slate-300 hidden sm:inline">{username}</span>
          </div>
        </div>
      </header>

      <div className="flex flex-col sm:flex-row gap-4">
        {/* Game navigation — horizontal row on mobile, vertical rail on desktop; only
            Rummy is live, the rest are placeholders for future games. */}
        <nav className="flex sm:flex-col gap-2 sm:w-28 shrink-0 overflow-x-auto sm:overflow-visible pb-1 sm:pb-0">
          {GAMES.map((g) => (
            <div
              key={g.key}
              className={`lobby-game-card rounded-xl px-3 py-3 text-center text-xs font-medium transition-transform shrink-0 w-20 sm:w-auto ${
                g.enabled ? "selected" : "opacity-40 cursor-not-allowed grayscale"
              }`}
              title={g.enabled ? undefined : "Coming soon"}
            >
              <div className="text-2xl mb-1">{g.icon}</div>
              {g.label}
              {!g.enabled && <div className="text-[10px] opacity-70 mt-0.5">Coming soon</div>}
            </div>
          ))}
        </nav>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex rounded-t-lg overflow-hidden">
                {(["real_money", "free", "pool"] as Mode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`lobby-tab px-4 py-2 text-sm rounded-t-lg ${mode === m ? "active" : ""}`}
                  >
                    {m === "real_money" ? "Points" : m === "free" ? "Practice" : "Pool"}
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
            <div className="flex items-center gap-3 text-sm" style={{ color: "var(--lobby-tab-active-text)" }}>
              {(["all", 2, 4] as PlayerFilter[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setPlayerFilter(f)}
                  className="flex items-center gap-1.5 cursor-pointer bg-transparent"
                >
                  <span
                    className={`lobby-filter-box w-4 h-4 rounded flex items-center justify-center ${
                      playerFilter === f ? "active" : ""
                    }`}
                  >
                    {playerFilter === f && <span className="lobby-filter-check text-xs leading-none">✓</span>}
                  </span>
                  {f === "all" ? "ALL" : `${f} Player`}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl overflow-hidden mb-4">
            <div>
              <div className="lobby-table-header grid grid-cols-4 sm:grid-cols-5 gap-2 px-4 py-2 text-xs uppercase">
                <span>{mode === "free" ? "Chips" : "Point Value"}</span>
                <span className="hidden sm:block">{mode === "pool" ? "Pool Limit" : "Min Entry"}</span>
                <span>Max Players</span>
                <span>Online</span>
                <span></span>
              </div>

              {tiers.map((tier) => {
                const online = getOnlinePlayers(tier);
                const busy = joiningTierId === tier.id && searchStatus === "searching";
                return (
                  <div
                    key={tier.id}
                    className="lobby-table-row grid grid-cols-4 sm:grid-cols-5 gap-2 px-4 py-3 items-center last:border-0"
                  >
                    <span className="lobby-money-text">
                      {mode === "free" ? "160 chips" : `₹${tier.pointValue}`}
                    </span>
                    <span className="lobby-money-text hidden sm:block">
                      {mode === "pool" ? `${tier.poolLimit} pts` : `₹${(tier.pointValue ?? 0) * 80}`}
                    </span>
                    <span className="lobby-player-icon flex items-center gap-1 font-semibold">
                      <Users size={16} /> {tier.maxPlayers}
                    </span>
                    <span className="lobby-online-icon flex items-center gap-1 font-semibold">
                      <Users size={16} /> {online}
                    </span>
                    <button
                      className="lobby-play-btn rounded-full justify-self-end px-4 py-1.5 text-sm"
                      disabled={busy}
                      onClick={() => joinTier(tier)}
                    >
                      {busy ? "Joining…" : "Play Now"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          {joinRowError && <p className="text-red-400 text-xs mb-2">{joinRowError}</p>}

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
      </div>

      {searchStatus !== "idle" && (
        <MatchSearchOverlay
          status={searchStatus}
          elapsedSeconds={search.elapsedSeconds}
          solo={search.solo}
          errorMessage={search.errorMessage}
          onCancel={search.cancel}
          onTryAgain={() => {
            const tier = tiers.find((t) => t.id === joiningTierId);
            search.reset();
            if (tier) joinTier(tier);
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
