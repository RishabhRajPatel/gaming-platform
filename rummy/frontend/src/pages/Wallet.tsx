import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  PaymentsApi,
  WalletApi,
  type Transaction,
  type Wallet as WalletBalance,
  type Withdrawal,
} from "../services/api";

const QUICK_AMOUNTS = [100, 500, 1000, 2000];

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

function rupees(paise: number) {
  return `₹${(paise / 100).toFixed(2)}`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const TXN_LABELS: Record<string, string> = {
  deposit: "Added cash",
  withdrawal: "Withdrawal",
  game_stake: "Table stake",
  game_payout: "Game winnings",
  bonus: "Bonus",
  adjustment: "Adjustment",
};

const WITHDRAWAL_STYLES: Record<string, string> = {
  requested: "bg-slate-800 text-slate-300 border-slate-600",
  approved: "bg-blue-900/60 text-blue-300 border-blue-700",
  processed: "bg-green-900/60 text-green-300 border-green-700",
  rejected: "bg-red-900/60 text-red-300 border-red-700",
};

export default function Wallet() {
  const navigate = useNavigate();
  const [wallet, setWallet] = useState<WalletBalance | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [withdrawals, setWithdrawals] = useState<Withdrawal[]>([]);

  const [addAmount, setAddAmount] = useState(500);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [withdrawAmount, setWithdrawAmount] = useState(100);
  const [withdrawing, setWithdrawing] = useState(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawOk, setWithdrawOk] = useState(false);

  function refresh() {
    WalletApi.get().then(setWallet).catch(() => {});
    WalletApi.transactions().then(setTxns).catch(() => {});
    WalletApi.withdrawals().then(setWithdrawals).catch(() => {});
  }

  useEffect(refresh, []);

  async function addCash() {
    setAddError(null);
    setAdding(true);
    try {
      const order = await PaymentsApi.deposit(addAmount * 100);
      const ok = await loadRazorpayScript();
      if (!ok || !window.Razorpay) {
        setAddError("Could not load the payment provider. Check your connection and try again.");
        return;
      }
      const rzp = new window.Razorpay({
        key: order.razorpay_key_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: "Deals Rummy",
        description: "Add cash to wallet",
        order_id: order.razorpay_order_id,
        handler: () => {
          // The wallet is credited server-side by the Razorpay webhook, not here —
          // this just gives the player quick feedback and a nudge to refresh.
          setTimeout(refresh, 2000);
        },
        theme: { color: "#d4af37" },
      });
      rzp.open();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setAddError(
        detail?.includes("not configured")
          ? "Payments aren't set up in this environment yet (no Razorpay keys configured on the server)."
          : detail ?? "Could not start the payment. Please try again."
      );
    } finally {
      setAdding(false);
    }
  }

  async function requestWithdraw() {
    setWithdrawError(null);
    setWithdrawOk(false);
    setWithdrawing(true);
    try {
      await WalletApi.withdraw(withdrawAmount * 100);
      setWithdrawOk(true);
      refresh();
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setWithdrawError(detail ?? "Could not request withdrawal.");
    } finally {
      setWithdrawing(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6">
      <header className="flex items-center gap-3 mb-6">
        <button className="btn-ghost px-2 py-1" onClick={() => navigate("/lobby")}>
          ← Lobby
        </button>
        <h1 className="text-2xl font-display font-bold text-gold-500">💰 Wallet</h1>
      </header>

      {/* Balances */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="card-surface p-4 text-center">
          <div className="text-xs text-slate-400 mb-1">Real cash</div>
          <div className="text-xl font-display font-bold text-gold-400">
            {wallet ? rupees(wallet.real_paise) : "—"}
          </div>
        </div>
        <div className="card-surface p-4 text-center">
          <div className="text-xs text-slate-400 mb-1">Bonus</div>
          <div className="text-xl font-display font-bold text-green-400">
            {wallet ? rupees(wallet.bonus_paise) : "—"}
          </div>
        </div>
        <div className="card-surface p-4 text-center">
          <div className="text-xs text-slate-400 mb-1">Chips</div>
          <div className="text-xl font-display font-bold text-slate-200">
            {wallet ? wallet.virtual_chips : "—"}
          </div>
        </div>
      </div>

      {/* Add cash */}
      <div className="card-surface p-4 mb-4">
        <h2 className="font-medium text-slate-100 mb-3">Add Cash</h2>
        <div className="flex flex-wrap gap-2 mb-3">
          {QUICK_AMOUNTS.map((amt) => (
            <button
              key={amt}
              onClick={() => setAddAmount(amt)}
              className={`px-3 py-1.5 rounded-full text-sm border ${
                addAmount === amt
                  ? "bg-gold-500 text-ink-950 border-gold-500"
                  : "border-ink-700 text-slate-300 hover:bg-ink-800"
              }`}
            >
              ₹{amt}
            </button>
          ))}
          <input
            type="number"
            min={1}
            className="input py-1.5 px-2 text-sm w-28"
            value={addAmount}
            onChange={(e) => setAddAmount(Math.max(1, Number(e.target.value)))}
          />
        </div>
        {addError && <p className="text-red-400 text-xs mb-2">{addError}</p>}
        <button className="btn-gold rounded-full px-5" disabled={adding} onClick={addCash}>
          {adding ? "Opening…" : `+ Add ₹${addAmount}`}
        </button>
      </div>

      {/* Withdraw */}
      <div className="card-surface p-4 mb-6">
        <h2 className="font-medium text-slate-100 mb-3">Withdraw</h2>
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <input
            type="number"
            min={1}
            className="input py-1.5 px-2 text-sm w-28"
            value={withdrawAmount}
            onChange={(e) => setWithdrawAmount(Math.max(1, Number(e.target.value)))}
          />
          <button
            className="btn-ghost rounded-full px-5"
            disabled={withdrawing}
            onClick={requestWithdraw}
          >
            {withdrawing ? "Requesting…" : `↓ Withdraw ₹${withdrawAmount}`}
          </button>
        </div>
        {withdrawError && <p className="text-red-400 text-xs">{withdrawError}</p>}
        {withdrawOk && <p className="text-green-400 text-xs">Withdrawal requested — pending approval.</p>}

        {withdrawals.length > 0 && (
          <div className="mt-3 space-y-1">
            {withdrawals.map((w) => (
              <div key={w.id} className="flex items-center justify-between text-sm bg-ink-900/60 rounded px-3 py-1.5">
                <span className="text-slate-300">{rupees(w.amount_paise)}</span>
                <span className="text-slate-500 text-xs">{formatDate(w.created_at)}</span>
                <span
                  className={`text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full border ${
                    WITHDRAWAL_STYLES[w.status] ?? "bg-ink-800 text-slate-400 border-ink-600"
                  }`}
                >
                  {w.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Transaction history */}
      <div className="card-surface overflow-hidden">
        <h2 className="font-medium text-slate-100 px-4 pt-4 pb-2">Transaction History</h2>
        {txns.length === 0 ? (
          <p className="text-slate-500 text-sm px-4 pb-4">No transactions yet.</p>
        ) : (
          <div className="divide-y divide-ink-800">
            {txns.map((t) => (
              <div key={t.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <div>
                  <div className="text-slate-200">{TXN_LABELS[t.txn_type] ?? t.txn_type}</div>
                  <div className="text-xs text-slate-500">{formatDate(t.created_at)}</div>
                </div>
                <div className="text-right">
                  <div className={t.amount_paise >= 0 ? "text-green-400" : "text-red-400"}>
                    {t.amount_paise >= 0 ? "+" : ""}
                    {t.kind === "virtual" ? t.amount_paise : rupees(t.amount_paise)}
                  </div>
                  <div className="text-xs text-slate-500">
                    bal: {t.kind === "virtual" ? t.balance_after : rupees(t.balance_after)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
