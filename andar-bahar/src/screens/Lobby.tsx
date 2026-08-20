import { useEffect, useState } from "react";
import {
  createDepositOrder,
  findOrCreateTable,
  getWallet,
  listTables,
  loadRazorpayScript,
  type TableOut,
  type Wallet,
} from "../services/api";
import { ensureAuth, lastAuthError } from "../services/auth";

type Mode = "virtual" | "real";

// Mirrors the reference lobby's Andar Bahar tier list (Min Bet / Max Bet / Min
// Entry). andar_bahar tables aren't parameterized by stake server-side — any
// table takes any stake >=1 — so a "tier" only sets this client's min/max bet
// range once seated; Min Entry is purely an affordability gate on the wallet,
// same idea as Rummy/Teen Patti's Play Now vs Add Cash.
interface Tier {
  minBet: number;
  maxBet: number;
  minEntry: number;
}
const TIERS: Tier[] = [
  { minBet: 1, maxBet: 512, minEntry: 100 },
  { minBet: 5, maxBet: 2560, minEntry: 500 },
  { minBet: 20, maxBet: 10240, minEntry: 2000 },
  { minBet: 50, maxBet: 25600, minEntry: 5000 },
];
const BETTING_SECONDS = 15;

function fmt(mode: Mode, v: number): string {
  return mode === "virtual" ? `${v} chips` : `₹${v}`;
}

export function Lobby({
  serverUrl,
  onJoin,
  onBack,
}: {
  serverUrl: string;
  onJoin: (tableId: string, tier: Tier, mode: Mode) => void;
  onBack: () => void;
}) {
  const [mode, setMode] = useState<Mode>("virtual");
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [tables, setTables] = useState<TableOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joiningTier, setJoiningTier] = useState<number | null>(null);

  async function refresh() {
    const ok = await ensureAuth(serverUrl);
    if (!ok) {
      setError(lastAuthError ? `Could not connect: ${lastAuthError}` : "Could not connect. Check the server URL in Settings.");
      setLoading(false);
      return;
    }
    const [w, t] = await Promise.all([getWallet(serverUrl), listTables(serverUrl)]);
    setWallet(w);
    setTables(t);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverUrl]);

  const haveBalance = wallet ? (mode === "virtual" ? wallet.virtual_chips : wallet.real_paise) : 0;
  // Tables aren't tier-partitioned server-side, so every row for this mode
  // shares the same live count — the total currently seated across all open
  // tables of this mode.
  const onlineForMode = tables.filter((t) => t.mode === mode).reduce((sum, t) => sum + t.online_players, 0);

  async function playNow(tier: Tier, idx: number) {
    setJoiningTier(idx);
    setError(null);
    try {
      const table = await findOrCreateTable(serverUrl, mode, BETTING_SECONDS);
      onJoin(table.id, tier, mode);
    } catch {
      setError("Could not join a table right now — try again.");
    } finally {
      setJoiningTier(null);
    }
  }

  async function addCash() {
    setError(null);
    try {
      const rupeesStr = window.prompt("Add how much? (₹)", "500");
      if (rupeesStr === null) return;
      const rupees = Math.max(1, Math.round(Number(rupeesStr) || 0));
      const order = await createDepositOrder(serverUrl, rupees * 100);
      if (!(await loadRazorpayScript()) || !window.Razorpay) {
        setError("Could not load the payment provider. Check your connection.");
        return;
      }
      new window.Razorpay({
        key: order.razorpay_key_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: "Andar Bahar",
        description: "Add cash to wallet",
        order_id: order.razorpay_order_id,
        handler: () => setTimeout(refresh, 2000),
        theme: { color: "#d4af37" },
      }).open();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the payment.");
    }
  }

  return (
    <div className="lobby">
      <div className="lobby-top">
        <button className="iconbtn" onClick={onBack}>←</button>
        <span className="brand" style={{ fontSize: 18 }}>Andar Bahar</span>
        <span className="balance"><small>{mode === "virtual" ? "♠" : "₹"}</small> {haveBalance}</span>
      </div>

      <div className="lobby-tabs">
        <button className={`lobby-tab${mode === "virtual" ? " active" : ""}`} onClick={() => setMode("virtual")}>
          Practice
        </button>
        <button className={`lobby-tab${mode === "real" ? " active" : ""}`} onClick={() => setMode("real")}>
          Points
        </button>
      </div>

      {error && <p className="hint" style={{ color: "#ff9a8a" }}>{error}</p>}
      {loading ? (
        <p className="hint">Loading…</p>
      ) : (
        <div className="lobby-table">
          <div className="lobby-row lobby-head">
            <span>Min Bet</span><span>Max Bet</span><span>Min Entry</span><span>Online</span><span></span>
          </div>
          {TIERS.map((tier, idx) => {
            const canAfford = haveBalance >= tier.minEntry;
            return (
              <div className="lobby-row" key={idx}>
                <span>{fmt(mode, tier.minBet)}</span>
                <span>{fmt(mode, tier.maxBet)}</span>
                <span>{fmt(mode, tier.minEntry)}</span>
                <span>{onlineForMode}</span>
                {/* Practice is free chips — never gated behind Add Cash, only Points is. */}
                {mode === "virtual" || canAfford ? (
                  <button className="action" disabled={joiningTier === idx} onClick={() => playNow(tier, idx)}>
                    {joiningTier === idx ? "Joining…" : "Play Now"}
                  </button>
                ) : (
                  <button className="action secondary" onClick={addCash}>Add Cash</button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export type { Tier, Mode };
