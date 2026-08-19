import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Users, MessageCircle, Smile, Settings, Flag,
  Layers3, Trash2, RotateCcw, Sparkles, Shuffle, Trophy,
} from "lucide-react";
import PlayingCard from "../components/game/PlayingCard";
import RulesModal from "../components/RulesModal";
import { useGameSocket } from "../hooks/useGameSocket";
import { autoArrange, classifyGroup, deadwoodPoints, isWild, parseCard, sortHand } from "../services/melds";
import { TableApi, type Table } from "../services/api";
import type { TableState } from "../services/gameTypes";
import { useAuth } from "../store/auth";

const FIRST_DROP_POINTS = 20;
const MIDDLE_DROP_POINTS = 40;

/** A random card code purely for the decorative toss flip — never a real card from
 * anyone's hand or the deck, just flavor while the toast names the actual (server-
 * decided) opening player. */
function randomCardCode(): string {
  const ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"];
  const suits = ["S", "H", "D", "C"];
  const rank = ranks[Math.floor(Math.random() * ranks.length)];
  const suit = suits[Math.floor(Math.random() * suits.length)];
  return `${rank}${suit}0`;
}

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-900/60 text-green-300 border-green-700",
  dropped: "bg-slate-800 text-slate-400 border-slate-600",
  won: "bg-gold-500/20 text-gold-400 border-gold-600",
  lost: "bg-red-900/60 text-red-300 border-red-700",
  out: "bg-red-950 text-red-400 border-red-800",
};

/** A circular countdown ring around a player's avatar — depletes from `total` down to
 * 0. Purely visual (the numeric badges already told the story); the server is still
 * the sole authority on the real deadline, this just makes it legible at a glance. */
function TurnRing({ seconds, total, size }: { seconds: number; total: number; size: number }) {
  const stroke = 3;
  const radius = size / 2 - stroke / 2 - 0.5;
  const circumference = 2 * Math.PI * radius;
  const progress = total > 0 ? Math.max(0, Math.min(1, seconds / total)) : 0;
  const urgent = seconds <= 5;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none"
    >
      <circle cx={size / 2} cy={size / 2} r={radius} stroke="rgba(255,255,255,0.12)" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        stroke={urgent ? "#f87171" : "#facc15"}
        strokeWidth={stroke}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - progress)}
        className={`transition-[stroke-dashoffset] duration-1000 ease-linear ${urgent ? "animate-pulse" : ""}`}
      />
    </svg>
  );
}

function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={`inline-block mt-0.5 text-[9px] uppercase font-semibold px-1.5 py-0.5 rounded-full border ${
        STATUS_STYLES[status] ?? "bg-ink-800 text-slate-400 border-ink-600"
      }`}
    >
      {status}
    </span>
  );
}

function ResultOverlay({
  state, meId, onContinue, onBackToLobby, onPlayAgain, playAgainBusy,
}: {
  state: TableState;
  meId: string | null;
  onContinue: () => void;
  onBackToLobby: () => void;
  onPlayAgain: () => void;
  playAgainBusy: boolean;
}) {
  const isPool = state.pool_limit != null;
  const isGameOver = state.phase === "game_over";
  const winner = state.players.find((p) => p.id === state.winner_id);
  const iWon = winner?.id === meId;
  const me = state.players.find((p) => p.id === meId);
  const iWasEliminatedThisDeal = isPool && !isGameOver && me?.eliminated;
  const pool = state.players
    .filter((p) => p.id !== state.winner_id)
    .reduce((sum, p) => sum + p.deal_points, 0);

  return (
    <div className="absolute inset-0 rounded-[50%] bg-black/80 flex flex-col items-center justify-center gap-3 z-30 px-10 text-center">
      <p className="font-display text-2xl text-gold-400">
        {isGameOver
          ? isPool
            ? iWon ? "🏆 POOL WINNER" : "🏁 POOL OVER"
            : "🏁 GAME OVER"
          : iWasEliminatedThisDeal
            ? "🚫 YOU'RE OUT"
            : iWon
              ? "🏆 YOU WIN"
              : winner
                ? `🏆 ${winner.name} wins the deal`
                : "Deal over"}
      </p>
      <div className="w-full max-w-xs space-y-1">
        {state.players.map((p) => (
          <div key={p.id} className="flex justify-between text-sm bg-ink-900/60 rounded px-3 py-1">
            <span className={p.id === meId ? "text-gold-300 font-semibold" : "text-slate-200"}>
              {p.name}
              {isPool && p.eliminated && <span className="ml-1 text-[9px] text-red-400 uppercase">out</span>}
            </span>
            <span className="flex items-center gap-2">
              <span className={p.id === state.winner_id ? "text-green-400" : "text-red-400"}>
                {p.id === state.winner_id ? `+${pool}` : `-${p.deal_points}`}
              </span>
              {isPool && (
                <span className="text-[10px] text-slate-500 font-mono">
                  {p.total_score}/{state.pool_limit}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-slate-500 font-mono">Game ID: {state.table_id}</p>
      {isGameOver ? (
        <div className="flex gap-2">
          <button className="btn-gold rounded-full px-5" disabled={playAgainBusy} onClick={onPlayAgain}>
            {playAgainBusy ? "Creating…" : "🔁 Play Again"}
          </button>
          <button className="btn-ghost rounded-full px-5" onClick={onBackToLobby}>
            Back to Lobby
          </button>
        </div>
      ) : (
        <button className="btn-gold rounded-full px-6 mt-2" onClick={onContinue}>
          Continue
        </button>
      )}
    </div>
  );
}

export default function GameTable() {
  const { tableId = "" } = useParams();
  const token = useAuth((s) => s.token);
  const myUsername = useAuth((s) => s.username);
  const navigate = useNavigate();
  const { state, hand, connected, lastError, send } = useGameSocket(tableId, token);

  const [table, setTable] = useState<Table | null>(null);
  const [leaveConfirmOpen, setLeaveConfirmOpen] = useState(false);
  const [groups, setGroups] = useState<string[][]>([]);
  const [finishCard, setFinishCard] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dragCode, setDragCode] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const [resultDismissed, setResultDismissed] = useState(false);
  const [playAgainBusy, setPlayAgainBusy] = useState(false);
  const [tossMessage, setTossMessage] = useState<string | null>(null);
  const [tossFading, setTossFading] = useState(false);
  const [tossCards, setTossCards] = useState<[string, string] | null>(null);
  const tossShownForDeal = useRef<number | null>(null);
  const [settingsMenuOpen, setSettingsMenuOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);

  // Real device height, not just Tailwind's `short:` CSS breakpoint — cards need an
  // actually smaller layout box on landscape phones (~390px tall), not just a visual
  // shrink, or the hand tray still reserves full-size space and pushes the action
  // buttons off-screen.
  const [compactCards, setCompactCards] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-height: 480px)");
    setCompactCards(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setCompactCards(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  async function handlePlayAgain() {
    if (!table) return;
    setPlayAgainBusy(true);
    try {
      const fresh = await TableApi.create({
        name: table.name,
        mode: table.mode,
        max_players: table.max_players,
        num_deals: table.num_deals,
        entry_fee_paise: table.entry_fee_paise,
        pool_limit: table.pool_limit,
      });
      navigate(`/table/${fresh.id}`);
    } finally {
      setPlayAgainBusy(false);
    }
  }

  useEffect(() => {
    TableApi.get(tableId).then(setTable).catch(() => setTable(null));
  }, [tableId]);

  // Live turn countdown — purely visual; the server is the authority and will
  // auto-play (draw+discard) if the real deadline elapses, regardless of this display.
  useEffect(() => {
    if (!state || (state.phase !== "await_draw" && state.phase !== "await_discard")) {
      setSecondsLeft(null);
      return;
    }
    setSecondsLeft(table?.turn_seconds ?? 30);
    const id = setInterval(() => {
      setSecondsLeft((s) => (s !== null && s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, [state, table?.turn_seconds]);

  // "X won the toss and will play first" — purely a presentation of who the server
  // already picked as the opening player (see start_deal's dealer-relative seat pick);
  // the client never chooses this, it just narrates it once per fresh deal. The two
  // flipped cards are decorative flavor only — randomised client side each time, not
  // read from anyone's real hand.
  useEffect(() => {
    if (!state || state.phase !== "await_draw") return;
    if (tossShownForDeal.current === state.deal_number) return;
    tossShownForDeal.current = state.deal_number;
    const firstPlayer = state.players.find((p) => p.id === state.turn);
    if (!firstPlayer) return;
    setTossMessage(`${firstPlayer.name} won the toss and will play first.`);
    setTossFading(false);
    setTossCards([randomCardCode(), randomCardCode()]);
    const fadeTimer = setTimeout(() => setTossFading(true), 2700);
    const clearTimer = setTimeout(() => {
      setTossMessage(null);
      setTossCards(null);
    }, 3000);
    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(clearTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.phase, state?.deal_number, state?.turn]);

  function handleStart() {
    send({ action: "start" });
  }

  useEffect(() => {
    if (state?.phase !== "deal_over" && state?.phase !== "game_over") {
      setResultDismissed(false);
    }
  }, [state?.phase]);

  // Reconcile local grouping with the server hand: keep existing arrangement, drop
  // cards that left the hand (discarded/declared), and drop newly drawn cards into
  // their own trailing group so the player notices and places them.
  useEffect(() => {
    setGroups((prev) => {
      const kept = prev.map((g) => g.filter((c) => hand.includes(c))).filter((g) => g.length > 0);
      const placed = new Set(kept.flat());
      const fresh = hand.filter((c) => c !== finishCard && !placed.has(c));
      return fresh.length > 0 ? [...kept, fresh] : kept;
    });
    setFinishCard((prev) => (prev && hand.includes(prev) ? prev : null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hand]);

  const me = state?.players.find((p) => p.name === myUsername) ?? null;
  const myTurn = !!(state && me && state.turn === me.id);
  const phase = state?.phase ?? "connecting";
  const wildRank = state?.wild_rank ?? null;
  const opponents = state?.players.filter((p) => p.id !== me?.id) ?? [];

  // Auto-start: once enough players are seated, the deal begins on its own — no
  // manual "Start deal" click needed. If the table is already full, start almost
  // immediately; if only the 2-player minimum is met on a bigger table, give
  // stragglers a real window to join before dealing locks the table (starting the
  // instant 2/4 are seated would strand the other seats — they can't join mid-deal).
  // Only the seat-0 client actually sends the command, so two simultaneous clients
  // don't both fire it; a harmless server-side rejection either way.
  //
  // For deal_over specifically, wait for the player to dismiss the result overlay
  // first (resultDismissed) — auto-starting the instant the deal ends would yank
  // the result screen away before anyone's had a chance to read it.
  const autoStartedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!state || !me || !table) return;
    const ready =
      state.phase === "waiting" || (state.phase === "deal_over" && resultDismissed);
    if (!ready) return;
    if (state.players.length < 2) return;
    if (state.players[0]?.id !== me.id) return;
    const key = `${state.phase}-${state.deal_number}-${state.players.length}`;
    if (autoStartedFor.current === key) return;
    autoStartedFor.current = key;
    const isFull = state.players.length >= table.max_players;
    const t = setTimeout(handleStart, isFull ? 600 : 12000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.phase, state?.deal_number, state?.players.length, me?.id, resultDismissed, table?.max_players]);

  const pointValue = table && table.mode === "real_money" ? table.entry_fee_paise / 100 : null;
  const modeName = table ? (table.mode === "real_money" ? "Points Rummy" : "Practice Rummy") : "";
  const dropPoints = phase === "await_draw" && hand.length === 13 ? FIRST_DROP_POINTS : MIDDLE_DROP_POINTS;
  const dropCost = pointValue != null ? `₹${(dropPoints * pointValue).toFixed(0)}` : `${dropPoints}`;

  function toggleSelect(code: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  function shiftLeft(i: number) {
    setGroups((gs) => {
      if (i <= 0) return gs;
      const copy = gs.map((g) => [...g]);
      const moved = copy[i].shift();
      if (moved === undefined) return gs;
      copy[i - 1].push(moved);
      return copy.filter((g) => g.length > 0);
    });
  }

  function shiftRight(i: number) {
    setGroups((gs) => {
      if (i >= gs.length - 1) return gs;
      const copy = gs.map((g) => [...g]);
      const moved = copy[i].pop();
      if (moved === undefined) return gs;
      copy[i + 1].unshift(moved);
      return copy.filter((g) => g.length > 0);
    });
  }

  function groupSelected() {
    if (selected.size < 2) return;
    setGroups((gs) => {
      const order = gs.flat().filter((c) => selected.has(c));
      const remaining = gs.map((g) => g.filter((c) => !selected.has(c))).filter((g) => g.length > 0);
      return [...remaining, order];
    });
    setSelected(new Set());
  }

  function resetGroups() {
    const all = [...groups.flat(), ...(finishCard ? [finishCard] : [])];
    setGroups(all.length > 0 ? [all] : []);
    setFinishCard(null);
    setSelected(new Set());
  }

  function doSort() {
    const all = [...groups.flat(), ...(finishCard ? [finishCard] : [])];
    setGroups(all.length > 0 ? [sortHand(all)] : []);
    setFinishCard(null);
    setSelected(new Set());
  }

  function doAutoSort() {
    const all = [...groups.flat(), ...(finishCard ? [finishCard] : [])];
    setGroups(autoArrange(all, wildRank));
    setFinishCard(null);
    setSelected(new Set());
  }

  function toggleFinishSlot() {
    if (finishCard) {
      setGroups((gs) => [...gs, [finishCard]]);
      setFinishCard(null);
      return;
    }
    if (selected.size !== 1) return;
    const [code] = selected;
    setGroups((gs) => gs.map((g) => g.filter((c) => c !== code)).filter((g) => g.length > 0));
    setFinishCard(code);
    setSelected(new Set());
  }

  // ---- drag-and-drop: an alternative to Group selected/◀▶ for mouse users. Dropping
  // onto a group appends to it; dropping onto the tray end starts a new group.
  // Identifies the target group by one of its existing cards rather than its index,
  // since removing the dragged card can shift/prune indices before the drop resolves.
  function dropOnGroup(targetSample: string | null) {
    const code = dragCode;
    setDragCode(null);
    if (!code) return;
    setGroups((gs) => {
      const without = gs.map((g) => g.filter((c) => c !== code));
      if (targetSample === null) {
        return [...without.filter((g) => g.length > 0), [code]];
      }
      const targetIdx = without.findIndex((g) => g.includes(targetSample));
      if (targetIdx === -1) return [...without.filter((g) => g.length > 0), [code]];
      return without.map((g, i) => (i === targetIdx ? [...g, code] : g)).filter((g) => g.length > 0);
    });
    if (finishCard === code) setFinishCard(null);
  }

  function dropOnFinishSlot() {
    const code = dragCode;
    setDragCode(null);
    if (!code) return;
    setGroups((gs) => {
      const without = gs.map((g) => g.filter((c) => c !== code)).filter((g) => g.length > 0);
      return finishCard ? [...without, [finishCard]] : without;
    });
    setFinishCard(code);
  }

  function doDiscard() {
    if (selected.size !== 1) return;
    const [code] = selected;
    send({ action: "discard", card: code });
    setSelected(new Set());
  }

  function doDeclare() {
    if (!finishCard) return;
    send({ action: "declare", groups });
    setSelected(new Set());
  }

  const canDiscard = myTurn && phase === "await_discard" && selected.size === 1;
  const canDeclare = myTurn && phase === "await_discard" && finishCard != null;
  // Matches the backend's own guard (drop() only allows AWAIT_DRAW/AWAIT_DISCARD) —
  // myTurn alone isn't enough, since current_player() defaults to the first seated
  // player even before a deal starts, which made Drop look clickable while WAITING.
  const canDrop = myTurn && (phase === "await_draw" || phase === "await_discard");
  const seatedCount = state?.players.length ?? 0;
  const emptySeats = table ? Math.max(0, table.max_players - seatedCount) : 0;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header
        className="relative flex items-center justify-between px-4 py-2.5 short:py-0.5 gap-3 backdrop-blur shadow-lg z-10"
        style={{ background: "rgba(9, 11, 24, 0.92)" }}
      >
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-gold-500/60 to-transparent" />
        <div className="flex items-center gap-3">
          <button className="btn-ghost px-2 py-1 flex items-center gap-1.5" onClick={() => setLeaveConfirmOpen(true)}>
            <ArrowLeft size={16} />
            Lobby
          </button>
          <span className="hidden sm:flex items-center gap-1.5 font-display font-bold text-gold-500 tracking-wide">
            🃏 Deals Rummy
          </span>
        </div>
        <div
          className="flex-1 flex justify-center items-center gap-3 text-xs px-4 py-1.5 font-medium max-w-md rounded-xl"
          style={{ background: "rgba(10, 8, 25, 0.85)", color: "#F4E6C1" }}
        >
          {table && (
            <span className="flex items-center gap-1.5">
              <Users size={13} style={{ color: "#49D78C" }} />
              Select Players: {table.max_players}
            </span>
          )}
          {table && <span style={{ color: "#FFE02B" }}>•</span>}
          {table && <span>{modeName}</span>}
          {pointValue != null && (
            <>
              <span style={{ color: "#FFE02B" }}>•</span>
              <span style={{ color: "#FFE02B" }}>Point Value: {pointValue.toFixed(1)}</span>
            </>
          )}
        </div>
        <div className="text-xs text-right shrink-0 flex items-center gap-2">
          <span className={`flex items-center gap-1 ${connected ? "text-green-400" : "text-red-400"}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
            {connected ? "live" : "reconnecting"}
          </span>
          {state && (
            <span className="hidden md:inline text-slate-400">
              {state.pool_limit != null ? `Pool ${state.pool_limit} · Deal ${state.deal_number}` : `Deal ${state.deal_number}/${state.num_deals}`}
            </span>
          )}
          <span className="uppercase px-2 py-0.5 rounded-full bg-ink-800 border border-ink-700 text-gold-400 font-semibold text-[10px]">
            {phase.replace("_", " ")}
          </span>
          {secondsLeft !== null && (
            <span
              className={`px-2 py-0.5 rounded-full border font-mono font-bold text-[11px] ${
                secondsLeft <= 5
                  ? "bg-red-900/60 border-red-600 text-red-300 animate-pulse"
                  : "bg-ink-800 border-ink-700 text-slate-200"
              }`}
            >
              ⏱ 0:{secondsLeft.toString().padStart(2, "0")}
            </span>
          )}
        </div>
      </header>

      {/* Table felt */}
      <main
        className="flex-1 flex items-center justify-center p-4 sm:p-8 short:p-1"
        style={{
          background:
            "radial-gradient(circle at 50% 20%, #24264A 0%, #17182F 55%, #090B18 100%)",
        }}
      >
        <div
          className="relative w-full max-w-4xl short:max-w-[210px] aspect-[2/1] rounded-[50%] short:rounded-3xl border-[8px] short:border-4 flex flex-col items-center justify-evenly short:gap-0.5 px-8 sm:px-20 short:px-2 py-6 short:py-0.5"
          style={{
            borderColor: "#11152A",
            background:
              "radial-gradient(ellipse at center, #20C98B 0%, #0DAA7B 45%, #007052 100%)",
            boxShadow:
              "0 0 0 4px #242743, 0 0 0 10px #0B1020, 0 12px 35px rgba(0,0,0,0.65), inset 0 0 80px rgba(0,0,0,0.35)",
          }}
        >
          {/* Faint felt watermark */}
          <div className="absolute inset-0 rounded-[50%] flex items-center justify-center pointer-events-none overflow-hidden opacity-[0.05]">
            <span className="font-display font-bold text-[6rem] tracking-widest text-gold-200 select-none">
              RUMMY
            </span>
          </div>
          {/* Opponents */}
          <div className="flex justify-center gap-6 flex-wrap">
            {opponents.map((p) => (
              <div key={p.id} className="text-center relative">
                {/* Card-back fan sized to their real hand count — decorative, not interactive */}
                <div className="short:hidden flex justify-center -space-x-4 mb-1 h-6">
                  {Array.from({ length: Math.min(p.hand_count, 13) }).map((_, i, arr) => (
                    <div
                      key={i}
                      className="w-4 h-6 rounded-sm border border-gold-700/50 bg-[repeating-linear-gradient(45deg,#3a2610,#3a2610_2px,#1d1409_2px,#1d1409_4px)]"
                      style={{ transform: `rotate(${(i - (arr.length - 1) / 2) * 4}deg)` }}
                    />
                  ))}
                </div>
                <div className="relative w-14 h-14 sm:w-16 sm:h-16 short:!w-8 short:!h-8 mx-auto">
                  <div
                    className={`absolute inset-0 rounded-full bg-gradient-to-br from-ink-700 to-ink-900 border-2 flex items-center justify-center font-display font-bold text-lg ${
                      state?.turn === p.id ? "border-gold-500 shadow-glow" : "border-ink-600"
                    }`}
                  >
                    {p.name.slice(0, 2).toUpperCase()}
                  </div>
                  {state?.turn === p.id && secondsLeft !== null && (
                    <TurnRing seconds={secondsLeft} total={table?.turn_seconds ?? 30} size={64} />
                  )}
                  {state?.turn === p.id && secondsLeft !== null && (
                    <span className="absolute -top-1 -right-1 short:!-top-0.5 short:!-right-0.5 w-6 h-6 short:!w-3.5 short:!h-3.5 rounded-full bg-ink-950 border-2 border-gold-500 flex items-center justify-center text-[10px] short:!text-[6px] font-mono font-bold text-gold-300">
                      {secondsLeft}
                    </span>
                  )}
                </div>
                <div className="text-sm font-medium text-slate-100 mt-1 short:text-[10px] short:mt-0">{p.name}</div>
                <div className="text-xs text-slate-300 short:hidden">🪙 {p.chips} · 🂠 {p.hand_count}</div>
                {state?.pool_limit != null && (
                  <div className="text-[10px] text-slate-500 font-mono short:hidden">
                    {p.total_score}/{state.pool_limit}
                  </div>
                )}
                <div className="short:hidden">
                  <StatusPill status={p.eliminated ? "out" : p.status} />
                </div>
              </div>
            ))}
            {phase === "waiting" &&
              Array.from({ length: emptySeats }).map((_, i) => (
                <div key={`empty-${i}`} className="text-center opacity-40">
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full border-2 border-dashed border-ink-600 flex items-center justify-center mx-auto">
                    <span className="text-2xl text-slate-600">?</span>
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Empty seat</div>
                </div>
              ))}
          </div>

          {phase === "waiting" && (
            <p className="text-center text-sm text-slate-300">
              {seatedCount < 2
                ? `Waiting for players to join (${seatedCount}/2 minimum)…`
                : `${seatedCount} seated — ready to start whenever you are.`}
            </p>
          )}

          {/* Center: wild joker, stock, finish slot, discard */}
          <div className="flex justify-center items-center gap-4 sm:gap-6 short:gap-2">
            <div className="text-center">
              <div className="text-[10px] text-slate-300 mb-1 short:hidden">Wild</div>
              {state?.wild_joker ? (
                <PlayingCard code={state.wild_joker} wild small />
              ) : (
                <div className="w-9 h-14 rounded-md bg-ink-800/60" />
              )}
            </div>

            <button className="text-center" disabled={!myTurn || phase !== "await_draw"}
                    onClick={() => send({ action: "draw", source: "stock" })}>
              <PlayingCard code="" faceDown small={compactCards} />
              <div className="text-[10px] text-slate-300 mt-1 short:hidden">CLOSED ({state?.stock_count ?? 0})</div>
            </button>

            {(() => {
              const finishDisabled = !finishCard && selected.size !== 1;
              return (
                // A <div> here, not a <button> — PlayingCard already renders its own
                // <button> internally, and nesting buttons breaks click handling in
                // some browsers (invalid HTML; React warns on it). The click on the
                // inner card bubbles up to this handler naturally.
                <div
                  role="button"
                  tabIndex={0}
                  className={`text-center w-14 h-20 rounded-lg border-2 flex items-center justify-center text-[9px] uppercase font-semibold whitespace-pre-line select-none ${
                    finishDisabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
                  } ${finishCard ? "border-gold-500 bg-ink-900/40" : "border-dashed border-slate-400/50 text-slate-300"} ${
                    dragCode ? "ring-2 ring-gold-400" : ""
                  }`}
                  onClick={finishDisabled ? undefined : toggleFinishSlot}
                  onKeyDown={(e) => {
                    if (!finishDisabled && (e.key === "Enter" || e.key === " ")) toggleFinishSlot();
                  }}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={dropOnFinishSlot}
                >
                  {finishCard ? <PlayingCard code={finishCard} small /> : "Finish\nSlot"}
                </div>
              );
            })()}

            {(() => {
              const canPickDiscard = myTurn && phase === "await_draw";
              return (
                <div
                  role="button"
                  tabIndex={0}
                  className={`text-center ${canPickDiscard ? "cursor-pointer" : "opacity-50 cursor-not-allowed"}`}
                  onClick={canPickDiscard ? () => send({ action: "draw", source: "discard" }) : undefined}
                  onKeyDown={(e) => {
                    if (canPickDiscard && (e.key === "Enter" || e.key === " ")) {
                      send({ action: "draw", source: "discard" });
                    }
                  }}
                >
                  {state?.top_discard ? <PlayingCard code={state.top_discard} small={compactCards} /> :
                    <div className="w-14 h-20 rounded-md bg-ink-800/60" />}
                  <div className="text-[10px] text-slate-300 mt-1 short:hidden">OPEN ({state?.discard_count ?? 0})</div>
                </div>
              );
            })()}
          </div>

          {/* Me — bottom seat, mirrors the opponent seat at the top (kept smaller
              since my full hand is already visible in the tray below). */}
          {me && (
            <div className="text-center relative">
              <div className="relative w-11 h-11 sm:w-12 sm:h-12 short:!w-8 short:!h-8 mx-auto">
                <div
                  className={`absolute inset-0 rounded-full bg-gradient-to-br from-ink-700 to-ink-900 border-2 flex items-center justify-center font-display font-bold text-sm ${
                    myTurn ? "border-gold-500 shadow-glow" : "border-ink-600"
                  }`}
                >
                  {me.name.slice(0, 2).toUpperCase()}
                </div>
                {myTurn && secondsLeft !== null && (
                  <TurnRing seconds={secondsLeft} total={table?.turn_seconds ?? 30} size={48} />
                )}
                {myTurn && secondsLeft !== null && (
                  <span className="absolute -top-1 -right-1 short:!-top-0.5 short:!-right-0.5 w-5 h-5 short:!w-3.5 short:!h-3.5 rounded-full bg-ink-950 border-2 border-gold-500 flex items-center justify-center text-[9px] short:!text-[6px] font-mono font-bold text-gold-300">
                    {secondsLeft}
                  </span>
                )}
              </div>
              <div className="text-xs font-medium text-slate-100 mt-1 short:mt-0">{me.name} (You)</div>
              <div className="text-[11px] text-slate-300 short:hidden">🪙 {me.chips} · 🂠 {hand.length}</div>
              {state?.pool_limit != null && (
                <div className="text-[10px] text-slate-500 font-mono short:hidden">
                  {me.total_score}/{state.pool_limit}
                  {me.eliminated ? " (OUT)" : ""}
                </div>
              )}
              <div className="short:hidden">
                <StatusPill status={me.eliminated ? "out" : me.status} />
              </div>
            </div>
          )}

          {tossMessage && (
            <div
              className={`absolute inset-0 flex items-center justify-center z-20 pointer-events-none transition-opacity duration-500 ${
                tossFading ? "opacity-0" : "opacity-100"
              }`}
            >
              <div
                className="flex items-center gap-3 px-4 py-2.5 rounded-full text-sm font-medium text-center"
                style={{
                  background: "rgba(0, 42, 31, 0.92)",
                  border: "1px solid rgba(30, 210, 145, 0.25)",
                  color: "#F5F5E8",
                  boxShadow: "0 4px 15px rgba(0,0,0,0.35)",
                }}
              >
                {tossCards && <PlayingCard code={tossCards[0]} small />}
                <span>{tossMessage}</span>
                {tossCards && <PlayingCard code={tossCards[1]} small />}
              </div>
            </div>
          )}

          {state && (state.phase === "deal_over" || state.phase === "game_over") && !resultDismissed && (
            <ResultOverlay
              state={state}
              meId={me?.id ?? null}
              onContinue={() => setResultDismissed(true)}
              onBackToLobby={() => navigate("/lobby")}
              onPlayAgain={handlePlayAgain}
              playAgainBusy={playAgainBusy}
            />
          )}
        </div>
      </main>

      {/* Side tool docks — chat/emoji/settings/report aren't built yet, so these are
          inert placeholders rather than fake-working buttons. */}
      <div className="fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 flex-col gap-3 lg:flex">
        <button
          className="flex h-12 w-12 flex-col items-center justify-center rounded-2xl border border-white/10 bg-black/70 text-white/70 backdrop-blur-xl transition hover:border-purple-400/50 hover:text-white"
          onClick={() => alert("Chat — coming soon")}
        >
          <MessageCircle size={19} />
          <span className="mt-1 text-[9px]">Chat</span>
        </button>
        <button
          className="flex h-12 w-12 flex-col items-center justify-center rounded-2xl border border-white/10 bg-black/70 text-white/70 backdrop-blur-xl transition hover:border-purple-400/50 hover:text-white"
          onClick={() => alert("Emoji reactions — coming soon")}
        >
          <Smile size={19} />
          <span className="mt-1 text-[9px]">Emoji</span>
        </button>
      </div>
      <div className="fixed right-4 top-1/2 z-40 hidden -translate-y-1/2 flex-col gap-3 lg:flex">
        <div className="relative">
          <button
            className="flex h-12 w-12 flex-col items-center justify-center rounded-2xl border border-white/10 bg-black/70 text-white/70 backdrop-blur-xl transition hover:border-gold-400/50 hover:text-white"
            onClick={() => setSettingsMenuOpen((v) => !v)}
          >
            <Settings size={19} />
            <span className="mt-1 text-[9px]">Settings</span>
          </button>
          {settingsMenuOpen && (
            <div className="absolute right-full top-0 mr-2 w-40 rounded-xl border border-white/10 bg-ink-900/95 backdrop-blur-xl shadow-2xl overflow-hidden">
              <button
                className="w-full text-left px-4 py-2.5 text-sm text-slate-200 hover:bg-ink-800 flex items-center gap-2"
                onClick={() => {
                  setSettingsMenuOpen(false);
                  setRulesOpen(true);
                }}
              >
                📖 Rules
              </button>
              <button
                className="w-full text-left px-4 py-2.5 text-sm text-slate-200 hover:bg-ink-800"
                onClick={() => {
                  setSettingsMenuOpen(false);
                  alert("Sound settings — coming soon");
                }}
              >
                🔊 Sound
              </button>
            </div>
          )}
        </div>
        <button
          className="flex h-12 w-12 flex-col items-center justify-center rounded-2xl border border-white/10 bg-black/70 text-white/70 backdrop-blur-xl transition hover:border-red-400/50 hover:text-white"
          onClick={() => alert("Report — coming soon")}
        >
          <Flag size={19} />
          <span className="mt-1 text-[9px]">Report</span>
        </button>
      </div>

      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}

      {leaveConfirmOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="card-surface w-full max-w-sm p-6 text-center">
            <h2 className="font-display text-lg font-bold text-gold-400 mb-3">Leave Table</h2>
            <p className="text-sm text-slate-300 mb-6">Are you sure you want to leave the table?</p>
            <div className="flex gap-3">
              <button
                className="btn-ghost rounded-full px-4 py-2 flex-1"
                onClick={() => setLeaveConfirmOpen(false)}
              >
                No
              </button>
              <button
                className="btn-danger rounded-full px-4 py-2 flex-1"
                onClick={() => navigate("/lobby")}
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating toast for the last server-rejected action */}
      {lastError && (
        <div className="fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-full border border-red-800 bg-black/90 px-6 py-3 text-sm text-red-300 shadow-2xl backdrop-blur-xl">
          ⚠ {lastError}
        </div>
      )}

      {/* My hand: grouped melds with live valid/invalid feedback */}
      <footer className="border-t border-gold-600/20 bg-ink-900/60 backdrop-blur p-4 short:p-1 shadow-[0_-8px_24px_rgba(0,0,0,0.35)]">
        <div className="flex w-full gap-1.5 mb-3 short:mb-1 overflow-x-auto pb-1">
          {groups.map((group, i) => {
            const meldType = classifyGroup(group, wildRank);
            const valid = meldType !== "invalid";
            const points = deadwoodPoints(group, wildRank);
            return (
              <div
                key={i}
                className={`flex-1 min-w-[88px] flex flex-col items-center rounded-lg p-1.5 short:p-0.5 bg-ink-900/60 border transition-shadow ${
                  dragCode && !group.includes(dragCode)
                    ? "ring-2 ring-gold-400/60 border-gold-500/40"
                    : "border-ink-700"
                }`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => dropOnGroup(group.find((c) => c !== dragCode) ?? null)}
              >
                <div className="flex justify-center">
                  {group.map((code, ci) => (
                    <div key={code} className={ci > 0 ? "-ml-4" : ""} style={{ zIndex: ci }}>
                      <PlayingCard
                        code={code}
                        small={compactCards}
                        selected={selected.has(code)}
                        wild={isWild(parseCard(code), wildRank)}
                        onClick={() => toggleSelect(code)}
                        draggable
                        onDragStart={() => setDragCode(code)}
                        onDragEnd={() => setDragCode(null)}
                      />
                    </div>
                  ))}
                </div>
                <div
                  className={`flex items-center gap-1.5 mt-1.5 short:mt-0.5 px-2 py-0.5 short:py-0 rounded-full text-[11px] short:text-[9px] font-medium w-full justify-center ${
                    valid ? "bg-green-700/60 text-green-200" : "bg-red-800/60 text-red-200"
                  }`}
                >
                  <button
                    className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-black/20 disabled:opacity-20"
                    disabled={i === 0}
                    onClick={() => shiftLeft(i)}
                  >
                    ◀
                  </button>
                  <span className="capitalize">{valid ? meldType.replace("_", " ") : `Invalid (${points})`}</span>
                  <button
                    className="w-4 h-4 flex items-center justify-center rounded-full hover:bg-black/20 disabled:opacity-20"
                    disabled={i === groups.length - 1}
                    onClick={() => shiftRight(i)}
                  >
                    ▶
                  </button>
                </div>
              </div>
            );
          })}
          {dragCode && (
            <div
              className="flex items-center justify-center w-14 h-20 rounded-lg border-2 border-dashed border-gold-400/60 text-[10px] text-gold-300 text-center px-1 animate-pulse"
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => dropOnGroup(null)}
            >
              + New group
            </div>
          )}
        </div>

        <div className="flex justify-center mb-3 short:hidden">
          <div className="rounded-full border border-white/10 bg-black/50 px-4 py-1 text-xs text-white/60">
            {hand.length} {hand.length === 1 ? "Card" : "Cards"}
          </div>
        </div>

        <div className="flex flex-wrap justify-center gap-2 mb-3 short:mb-1 short:gap-1">
          {selected.size >= 2 && (
            <button className="btn-ghost flex items-center gap-1.5 short:px-2 short:py-1 short:text-xs" onClick={groupSelected}>
              <Layers3 size={15} className="text-purple-400" />
              Group
            </button>
          )}
          <button className="btn-ghost flex items-center gap-1.5 short:px-2 short:py-1 short:text-xs" disabled={hand.length === 0} onClick={doSort}>
            <Shuffle size={15} />
            Sort
          </button>
          <button className="btn-ghost flex items-center gap-1.5 short:px-2 short:py-1 short:text-xs" disabled={hand.length === 0} onClick={doAutoSort}>
            <Sparkles size={15} className="text-gold-400" />
            Auto Sort
          </button>
          <button className="btn-ghost flex items-center gap-1.5 short:px-2 short:py-1 short:text-xs" onClick={resetGroups}>
            <RotateCcw size={15} />
            Reset
          </button>
        </div>

        <div className="flex justify-between items-center flex-wrap gap-2">
          {me && (
            <div className="flex items-center gap-2 text-sm short:hidden">
              <div className="relative w-10 h-10 shrink-0">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-ink-700 to-ink-900 border-2 border-gold-500 flex items-center justify-center font-display font-bold">
                  {me.name.slice(0, 2).toUpperCase()}
                </div>
                {myTurn && secondsLeft !== null && (
                  <TurnRing seconds={secondsLeft} total={table?.turn_seconds ?? 30} size={40} />
                )}
              </div>
              <span className="text-slate-100 font-medium">{me.name}</span>
              <span className="text-gold-400">{me.chips} chips</span>
              <span className="text-slate-400">score: {me.deal_points}</span>
              {state?.pool_limit != null && (
                <span className={`font-mono ${me.eliminated ? "text-red-400" : "text-slate-500"}`}>
                  pool: {me.total_score}/{state.pool_limit}
                  {me.eliminated ? " (OUT)" : ""}
                </span>
              )}
            </div>
          )}
          <div className="flex gap-2 short:gap-1.5 short:w-full short:justify-between">
            {canDiscard && (
              <button className="btn-ghost rounded-full px-4 short:px-2 short:text-xs flex items-center gap-1.5" onClick={doDiscard}>
                <Trash2 size={15} />
                Discard
              </button>
            )}
            {canDrop && (
              <button className="btn-danger rounded-full px-4 short:px-2 short:text-xs flex items-center gap-1.5" onClick={() => send({ action: "drop" })}>
                <Flag size={15} />
                Drop {dropCost}
              </button>
            )}
            {canDeclare && (
              <button className="btn-gold rounded-full px-5 short:px-3 short:text-xs flex items-center gap-1.5" onClick={doDeclare}>
                <Trophy size={15} />
                Declare
              </button>
            )}
          </div>
        </div>
        <div className="mt-3 short:hidden flex items-center gap-3 rounded-2xl border border-white/10 bg-black/30 px-4 py-2.5 text-xs text-white/60">
          <span className="text-base shrink-0">💡</span>
          <span>
            Drag a card onto another group (or the Finish Slot) to move it, or select 2+ cards and
            "Group" — use ◀ ▶ to fine-tune, then select one card and tap the Finish Slot before Declare.
          </span>
        </div>
      </footer>
    </div>
  );
}
