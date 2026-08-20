import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Users, History, BarChart3, Volume2, VolumeX, Settings, Flag,
  Trash2, RotateCcw, Sparkles, Shuffle, Trophy, MessageCircle, Minus, Plus,
} from "lucide-react";
import PlayingCard from "../components/game/PlayingCard";
import "./GameTable.css";
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
  const tossTimers = useRef<{ fade?: ReturnType<typeof setTimeout>; clear?: ReturnType<typeof setTimeout> }>({});
  const [settingsMenuOpen, setSettingsMenuOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  // No sound effects exist yet, but the preference itself is real and persists —
  // this toggle isn't a decorative stand-in, it's what future sound effects will read.
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem("rummy_sound") !== "off");
  function toggleSound() {
    setSoundOn((v) => {
      const next = !v;
      localStorage.setItem("rummy_sound", next ? "on" : "off");
      return next;
    });
  }

  // The felt table is a wide oval — it only works in landscape. The installed
  // Android APK already force-locks landscape natively (manifest.webmanifest's
  // "orientation": "landscape" — PWABuilder's TWA wrapper reads that directly, no
  // JS involved). In a regular browser tab there's no reliable cross-browser way to
  // force rotation, so we best-effort request a lock (works on Chrome/Android once
  // fullscreen) and always fall back to a "please rotate" block for phones that
  // stay portrait — tablets/desktops in a tall window are exempt (width check keeps
  // this phone-only).
  const [portraitPhone, setPortraitPhone] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(orientation: portrait) and (max-width: 820px)");
    setPortraitPhone(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setPortraitPhone(e.matches);
    mq.addEventListener("change", onChange);

    const orientation = screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> };
    orientation?.lock?.("landscape").catch(() => {
      // Not supported outside fullscreen/standalone contexts — the rotate-prompt
      // overlay below is the fallback for those cases, not an error to surface.
    });

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
    // Timers are owned by a ref, not this effect's cleanup — turn/phase changing
    // later in the same deal (e.g. the first player draws within 3s) would otherwise
    // re-run this effect, cancel the pending hide-timers via cleanup, and then hit
    // the guard above and return before rescheduling — leaving the toast stuck
    // forever. Clearing+resetting here (only reached once per deal) avoids that.
    clearTimeout(tossTimers.current.fade);
    clearTimeout(tossTimers.current.clear);
    tossTimers.current.fade = setTimeout(() => setTossFading(true), 2700);
    tossTimers.current.clear = setTimeout(() => {
      setTossMessage(null);
      setTossCards(null);
    }, 3000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state?.phase, state?.deal_number, state?.turn]);

  useEffect(() => {
    const timers = tossTimers.current;
    return () => {
      clearTimeout(timers.fade);
      clearTimeout(timers.clear);
    };
  }, []);

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

  function ungroupSelected() {
    if (selected.size === 0) return;
    setGroups((gs) => {
      const pulled = gs.flat().filter((c) => selected.has(c));
      const remaining = gs.map((g) => g.filter((c) => !selected.has(c))).filter((g) => g.length > 0);
      return [...remaining, ...pulled.map((c) => [c])];
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
  const chipsLabel = me
    ? (pointValue != null ? `₹${me.chips}` : `${me.chips}`)
    : "—";

  if (portraitPhone) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4 p-6 text-center bg-[#050506]">
        <RotateCcw size={40} className="text-[#F4C542] animate-pulse" />
        <p className="text-slate-200 font-medium">Please rotate your device to landscape mode</p>
        <p className="text-slate-500 text-sm">Deals Rummy plays best in landscape.</p>
      </div>
    );
  }

  return (
    <div className="gt-shell">
      <header className="gt-header">
        <div className="gt-header-cluster">
          <button className="gt-chip" onClick={() => setLeaveConfirmOpen(true)}>
            <ArrowLeft size={14} /><span>Lobby</span>
          </button>
          <span className="gt-title">Deals Rummy</span>
        </div>
        <div className="gt-header-cluster">
          {table && (
            <span className="gt-chip">
              <Users size={12} className="text-[#49D78C]" />
              Players {table.max_players}
            </span>
          )}
          {table && <span className="gt-chip gt-hide-narrow">{modeName}</span>}
        </div>
        <div className="gt-header-cluster">
          <span className={`gt-chip ${connected ? "text-green-400" : "text-red-400"}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
            {connected ? "LIVE" : "OFFLINE"}
          </span>
          {state && (
            <span className="gt-chip uppercase text-[10px] text-[#F4C542] gt-hide-narrow">
              {phase.replace("_", " ")}
            </span>
          )}
          {secondsLeft !== null && (
            <span className={`gt-chip font-mono ${secondsLeft <= 5 ? "text-red-300 animate-pulse" : ""}`}>
              ⏱ 0:{secondsLeft.toString().padStart(2, "0")}
            </span>
          )}
          <div className="relative">
            <button className="gt-chip !px-2" onClick={() => setSettingsMenuOpen((v) => !v)} aria-label="Settings">
              <Settings size={15} />
            </button>
            {settingsMenuOpen && (
              <div className="absolute right-0 top-9 w-40 rounded-xl border border-white/10 bg-[#0D0B1B]/95 backdrop-blur-xl shadow-2xl overflow-hidden z-[70]">
                <button className="w-full text-left px-4 py-3 text-sm text-slate-200 hover:bg-white/5" onClick={() => { setSettingsMenuOpen(false); setRulesOpen(true); }}>📖 Rules</button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="gt-main">
        <div className="gt-rails gt-rails-left">
          <button type="button" className="gt-rail-btn" onClick={() => alert("History — coming soon")}><History size={15} /><span>History</span></button>
          <button type="button" className="gt-rail-btn" onClick={() => alert("Score — coming soon")}><BarChart3 size={15} /><span>Score</span></button>
          <button type="button" className="gt-rail-btn" onClick={() => alert("Chat — coming soon")}><MessageCircle size={15} /><span>Chat</span></button>
          <button type="button" className="gt-rail-btn" onClick={toggleSound}>
            {soundOn ? <Volume2 size={15} /> : <VolumeX size={15} />}
            <span>{soundOn ? "Sound" : "Muted"}</span>
          </button>
        </div>

        <div className="gt-rails gt-rails-right">
          <button type="button" className="gt-rail-btn" disabled={hand.length === 0} onClick={doSort}><Shuffle size={15} /><span>Sort</span></button>
          <button type="button" className="gt-rail-btn" disabled={hand.length === 0} onClick={doAutoSort}><Sparkles size={15} className="text-[#F4C542]" /><span>Auto Sort</span></button>
          <button type="button" className="gt-rail-btn" onClick={resetGroups}><RotateCcw size={15} /><span>Reset</span></button>
        </div>

        <div className="gt-table">
          <div className="gt-felt">
            <div className="gt-watermark">RUMMY</div>
          </div>

          <div className="relative z-10 pt-1 text-center">
            <div className="flex justify-center gap-5 flex-wrap px-6">
              {opponents.map((p) => (
                <div key={p.id} className="text-center relative">
                  <div className="relative w-10 h-10 mx-auto">
                    <div className={`absolute inset-0 rounded-full bg-gradient-to-br from-[#2B3045] to-[#090B14] border-2 flex items-center justify-center font-display font-bold text-sm ${state?.turn === p.id ? "border-[#F4C542] shadow-[0_0_18px_rgba(244,197,66,.45)]" : "border-white/30"}`}>{p.name.slice(0, 2).toUpperCase()}</div>
                    {state?.turn === p.id && secondsLeft !== null && <TurnRing seconds={secondsLeft} total={table?.turn_seconds ?? 30} size={40} />}
                    {state?.turn === p.id && secondsLeft !== null && <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#0B1020] border-2 border-[#F4C542] flex items-center justify-center text-[7px] font-mono font-bold text-[#F4C542]">{secondsLeft}</span>}
                    {(p.eliminated || p.status !== "active") && (
                      <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-red-900 border border-red-600 flex items-center justify-center text-[7px]">✕</span>
                    )}
                  </div>
                  <div className="text-[10px] font-semibold text-white mt-0.5 leading-tight">{p.name}</div>
                  <div className="text-[8px] text-white/70 leading-tight">🪙{p.chips} · 🂠{p.hand_count}</div>
                </div>
              ))}
              {phase === "waiting" && Array.from({ length: emptySeats }).map((_, i) => (
                <div key={`empty-${i}`} className="text-center opacity-40">
                  <div className="w-10 h-10 rounded-full border-2 border-dashed border-white/30 flex items-center justify-center mx-auto"><span className="text-lg text-white/40">?</span></div>
                  <div className="text-[9px] text-white/50 mt-0.5">Empty</div>
                </div>
              ))}
            </div>
          </div>

          <div className="gt-piles">
            <div className="text-center">
              {state?.wild_joker ? <PlayingCard code={state.wild_joker} wild small /> : <div className="w-12 h-[4.5rem] rounded-lg bg-black/20 border border-dashed border-white/25" />}
              <div className="gt-pile-label">Wild</div>
            </div>
            <button className="text-center disabled:opacity-60" disabled={!myTurn || phase !== "await_draw"} onClick={() => send({ action: "draw", source: "stock" })}>
              <PlayingCard code="" faceDown small />
              <div className="gt-pile-label">Closed ({state?.stock_count ?? 0})</div>
            </button>
            <div
              role="button"
              tabIndex={0}
              className={`text-center ${myTurn && phase === "await_draw" ? "cursor-pointer" : "opacity-60"}`}
              onClick={myTurn && phase === "await_draw" ? () => send({ action: "draw", source: "discard" }) : undefined}
            >
              {state?.top_discard ? <PlayingCard code={state.top_discard} small /> : <div className="w-12 h-[4.5rem] rounded-lg bg-black/20 border border-dashed border-white/25" />}
              <div className="gt-pile-label">Open ({state?.discard_count ?? 0})</div>
            </div>
            <div
              role="button"
              tabIndex={0}
              className={`gt-finish ${!finishCard && selected.size !== 1 ? "opacity-50 cursor-not-allowed" : "cursor-pointer"} ${finishCard ? "filled" : ""} ${dragCode ? "ring-2 ring-[#F4C542]" : ""}`}
              onClick={!finishCard && selected.size !== 1 ? undefined : toggleFinishSlot}
              onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && (finishCard || selected.size === 1)) toggleFinishSlot(); }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={dropOnFinishSlot}
            >
              {finishCard ? <PlayingCard code={finishCard} small /> : "Finish\nSlot"}
            </div>

            {tossMessage && (
              <div className={`absolute inset-0 flex items-center justify-center z-20 pointer-events-none transition-opacity duration-500 ${tossFading ? "opacity-0" : "opacity-100"}`}>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-medium text-center bg-[#002A1F]/95 border border-[#1ED291]/30 shadow-2xl max-w-[92%]">
                  {tossCards && <PlayingCard code={tossCards[0]} small />}
                  <span>{tossMessage}</span>
                  {tossCards && <PlayingCard code={tossCards[1]} small />}
                </div>
              </div>
            )}
          </div>

          {phase === "waiting" && (
            <p className="relative z-10 text-center text-[11px] text-white/80 px-5">
              {seatedCount < 2 ? `Waiting for players (${seatedCount}/2 minimum)…` : `${seatedCount} seated — ready to start.`}
            </p>
          )}

          {me && (
            <div className="relative z-10 text-center pb-1">
              <div className="relative w-9 h-9 mx-auto">
                <div className={`absolute inset-0 rounded-full bg-gradient-to-br from-[#2B3045] to-[#090B14] border-2 flex items-center justify-center font-display font-bold text-xs ${myTurn ? "border-[#F4C542] shadow-[0_0_18px_rgba(244,197,66,.45)]" : "border-white/30"}`}>{me.name.slice(0, 2).toUpperCase()}</div>
                {myTurn && secondsLeft !== null && <TurnRing seconds={secondsLeft} total={table?.turn_seconds ?? 30} size={36} />}
              </div>
            </div>
          )}

          {state && (state.phase === "deal_over" || state.phase === "game_over") && !resultDismissed && (
            <ResultOverlay state={state} meId={me?.id ?? null} onContinue={() => setResultDismissed(true)} onBackToLobby={() => navigate("/lobby")} onPlayAgain={handlePlayAgain} playAgainBusy={playAgainBusy} />
          )}
        </div>
      </main>

      <footer className="gt-footer">
        <div className="gt-hand">
          {groups.map((group, i) => {
            const meldType = classifyGroup(group, wildRank);
            const valid = meldType !== "invalid";
            const points = deadwoodPoints(group, wildRank);
            return (
              <div
                key={i}
                className={`gt-hand-group ${dragCode && !group.includes(dragCode) ? "ring-2 ring-[#F4C542]/60 border-[#F4C542]/40" : ""}`}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => dropOnGroup(group.find((c) => c !== dragCode) ?? null)}
              >
                <div className="gt-hand-cards">
                  {group.map((code, ci) => (
                    <div key={code} className="gt-hand-card" style={{ zIndex: ci }}>
                      <PlayingCard
                        code={code}
                        small
                        className="gt-card-hand"
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
                <div className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium ${valid ? "bg-green-700/60 text-green-200" : "bg-red-800/70 text-red-200"}`}>
                  <button className="w-3.5 h-3.5 flex items-center justify-center" disabled={i === 0} onClick={() => shiftLeft(i)}>◀</button>
                  <span className="whitespace-nowrap">{valid ? meldType.replace("_", " ") : `Invalid (${points})`}</span>
                  <button className="w-3.5 h-3.5 flex items-center justify-center" disabled={i === groups.length - 1} onClick={() => shiftRight(i)}>▶</button>
                </div>
              </div>
            );
          })}
          {dragCode && (
            <div className="shrink-0 w-14 h-20 rounded-lg border-2 border-dashed border-[#F4C542]/60 text-[9px] text-[#F4C542] flex items-center justify-center text-center animate-pulse" onDragOver={(e) => e.preventDefault()} onDrop={() => dropOnGroup(null)}>
              + New group
            </div>
          )}
        </div>

        <div className="gt-actions">
          <div className="gt-stat">
            <span className="gt-stat-box">{chipsLabel}</span>
            <span className="gt-stat-box">Total {me?.deal_points ?? 0}</span>
            {selected.size > 0 && (
              <button type="button" className="gt-icon-btn" onClick={ungroupSelected} aria-label="Ungroup"><Minus size={14} /></button>
            )}
            {selected.size >= 2 && (
              <button type="button" className="gt-icon-btn" onClick={groupSelected} aria-label="Group"><Plus size={14} /></button>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {canDiscard && (
              <button type="button" className="gt-btn-discard inline-flex items-center justify-center gap-1" onClick={doDiscard}>
                <Trash2 size={13} /> Discard
              </button>
            )}
            {canDrop && (
              <button type="button" className="gt-btn-drop inline-flex items-center justify-center gap-1" onClick={() => send({ action: "drop" })}>
                <Flag size={13} /> Drop {dropCost}
              </button>
            )}
            {canDeclare && (
              <button type="button" className="gt-btn-declare inline-flex items-center justify-center gap-1" onClick={doDeclare}>
                <Trophy size={13} /> Declare
              </button>
            )}
          </div>
        </div>
      </footer>

      {rulesOpen && <RulesModal onClose={() => setRulesOpen(false)} />}
      {leaveConfirmOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="card-surface w-full max-w-sm p-6 text-center">
            <h2 className="font-display text-lg font-bold text-gold-400 mb-3">Leave Table</h2>
            <p className="text-sm text-slate-300 mb-6">Are you sure you want to leave the table?</p>
            <div className="flex gap-3">
              <button className="btn-ghost rounded-full px-4 py-2 flex-1" onClick={() => setLeaveConfirmOpen(false)}>No</button>
              <button className="btn-danger rounded-full px-4 py-2 flex-1" onClick={() => navigate("/lobby")}>Yes</button>
            </div>
          </div>
        </div>
      )}
      {lastError && <div className="fixed bottom-28 left-1/2 z-50 -translate-x-1/2 rounded-full border border-red-800 bg-black/90 px-6 py-3 text-sm text-red-300 shadow-2xl backdrop-blur-xl">⚠ {lastError}</div>}
    </div>
  );
}
