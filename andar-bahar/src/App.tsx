import { useEffect, useRef, useState } from "react";
import { CardView } from "./components/CardView";
import { rankLabel, type Card } from "./game/deck";
import {
  PAYOUT,
  RoundResult,
  Settlement,
  Side,
  playRoundFromSeed,
  settleBet,
} from "./game/andarBahar";
import { placeBetRemote } from "./services/api";
import {
  getBalance,
  getClientSeed,
  getHistory,
  getServerUrl,
  nextNonce,
  pushHistory,
  setBalance as persistBalance,
  type HistoryEntry,
} from "./services/config";
import { Settings } from "./screens/Settings";
import { Lobby, type Tier, type Mode } from "./screens/Lobby";
import { OnlineTable } from "./screens/OnlineTable";
import { HistoryPanel } from "./components/HistoryPanel";
import { ProgressStepper } from "./components/ProgressStepper";

const CHIPS = [10, 50, 100, 500, 1000];
const STAKE_STEP = 10;
const BETTING_SECONDS = 15;
type Phase = "betting" | "closed" | "dealing" | "result";

const RULES_COPY: Record<"how" | "rules", { title: string; items: string[] }> = {
  how: {
    title: "How to Play",
    items: [
      "Pick a chip amount, or fine-tune it with the − / + stepper.",
      "Tap ANDAR or BAHAR to select a side (tap again to deselect).",
      "Tap Confirm Bet before the countdown reaches 0 — bets lock the instant you confirm.",
      "The Open Card is revealed and its rank becomes the target rank.",
      "Cards are dealt one at a time, alternating Andar and Bahar.",
      "The first card matching the target rank ends the round — that side wins.",
      "Tap New Round to play again.",
    ],
  },
  rules: {
    title: "Rule Book",
    items: [
      "Deck: one standard 52-card deck, no jokers. Only rank matters — suit never decides the winner.",
      "Target rank: set by the Open Card, revealed once betting closes.",
      "Start side: a black Open Card (♠/♣) deals to Andar first; a red one (♥/♦) deals to Bahar first.",
      "Dealing: cards alternate sides from the start side until a card of the target rank appears.",
      "First match wins: the round ends immediately on the first matching card — remaining cards are never dealt.",
      "Payouts: Andar pays 0.9× stake, Bahar pays 1.0× stake, net on a win.",
      "No tie: every round has exactly one winning side.",
      "Fair play: offline rounds use a seeded shuffle (client seed + nonce) you can reproduce; online rounds are settled by the server and are provably fair (server seed + hash returned with every bet).",
    ],
  },
};

export default function App() {
  const [screen, setScreen] = useState<"game" | "settings" | "lobby" | "online-table">("game");
  const [onlineTable, setOnlineTable] = useState<{ id: string; tier: Tier; mode: Mode } | null>(null);
  const [balance, setBalance] = useState(1000);
  const [serverUrl, setServerUrl] = useState("");
  const [stake, setStake] = useState(50);
  const [phase, setPhase] = useState<Phase>("betting");
  const [bet, setBet] = useState<Side | null>(null);
  const [selectedSide, setSelectedSide] = useState<Side | null>(null);
  const [showChipMenu, setShowChipMenu] = useState(false);

  const [middle, setMiddle] = useState<Card | null>(null);
  const [andar, setAndar] = useState<Card[]>([]);
  const [bahar, setBahar] = useState<Card[]>([]);
  const [result, setResult] = useState<{ won: boolean; text: string } | null>(null);
  const [timeLeft, setTimeLeft] = useState(BETTING_SECONDS);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const [rulesPopup, setRulesPopup] = useState<"how" | "rules" | null>(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    getBalance().then(setBalance);
    getServerUrl().then(setServerUrl);
    getHistory().then(setHistory);
    return () => {
      timers.current.forEach(clearTimeout);
      timers.current = [];
    };
  }, [screen]);

  // Betting countdown: only runs while betting is open. If it hits 0 with no
  // bet placed, the round is silently skipped (no charge) and the timer restarts.
  useEffect(() => {
    if (phase !== "betting") return;
    setTimeLeft(BETTING_SECONDS);
    const id = window.setInterval(() => {
      setTimeLeft((t) => (t <= 1 ? BETTING_SECONDS : t - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  // The table is a wide landscape layout. The installed Android APK already
  // force-locks landscape natively (AndroidManifest.xml's screenOrientation), so
  // this is the browser/dev-server fallback: best-effort request a lock (works on
  // Chrome/Android once fullscreen) and always fall back to a "please rotate"
  // overlay for phones that stay portrait — tablets/desktops in a tall window are
  // exempt (the width check keeps this phone-only).
  const [portraitPhone, setPortraitPhone] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(orientation: portrait) and (max-width: 820px)");
    setPortraitPhone(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setPortraitPhone(e.matches);
    mq.addEventListener("change", onChange);

    const orientation = window.screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> };
    orientation?.lock?.("landscape").catch(() => {
      // Not supported outside fullscreen/standalone contexts — the rotate-prompt
      // overlay above is the fallback for those cases, not an error to surface.
    });

    return () => mq.removeEventListener("change", onChange);
  }, []);

  function updateBalance(next: number) {
    setBalance(next);
    void persistBalance(next);
  }

  async function resolveRound(
    chosen: Side,
  ): Promise<{ round: RoundResult; balanceAfter: number; settlement: Settlement } | null> {
    // Try server first if configured; fall back to offline provably-fair play.
    if (serverUrl) {
      const clientSeed = await getClientSeed();
      const nonce = await nextNonce();
      const remote = await placeBetRemote(serverUrl, { bet: chosen, stake, clientSeed, nonce });
      // Server settlement is authoritative — don't recompute it client-side, in case
      // PAYOUT constants ever drift between the client and server engines.
      if (remote) return { round: remote.round, balanceAfter: remote.balance, settlement: remote.settlement };
    }
    // Offline
    const clientSeed = await getClientSeed();
    const nonce = await nextNonce();
    const round = playRoundFromSeed(`${clientSeed}:${nonce}`);
    const settlement = settleBet(chosen, stake, round.winner);
    const balanceAfter = balance - stake + settlement.returned;
    return { round, balanceAfter, settlement };
  }

  async function placeBet(chosen: Side) {
    if (phase !== "betting" || stake > balance) return;
    timers.current = []; // previous round's timeouts already fired; drop the stale ids
    setBet(chosen);
    setSelectedSide(null);
    setShowChipMenu(false);
    setResult(null);
    setAndar([]);
    setBahar([]);
    setPhase("closed"); // stops the betting timer; open-card reveal comes next
    updateBalance(balance - stake); // reserve stake immediately

    const outcome = await resolveRound(chosen);
    if (!outcome) {
      setPhase("betting");
      updateBalance(balance); // refund on failure
      return;
    }
    const { round, balanceAfter, settlement } = outcome;
    setMiddle(round.middle);
    setPhase("dealing");

    // animate the deal
    let i = 0;
    const step = () => {
      if (i >= round.steps.length) {
        setResult({
          won: settlement.won,
          text: settlement.won
            ? `${chosen.toUpperCase()} wins! +${settlement.payout}`
            : `${round.winner.toUpperCase()} wins. −${stake}`,
        });
        updateBalance(balanceAfter);
        setPhase("result");
        void pushHistory({
          id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          ts: Date.now(),
          openCard: round.middle,
          bet: chosen,
          stake,
          winner: round.winner,
          won: settlement.won,
          payout: settlement.payout,
        }).then(setHistory);
        return;
      }
      const s = round.steps[i];
      if (s.side === "andar") setAndar((a) => [...a, s.card]);
      else setBahar((b) => [...b, s.card]);
      i += 1;
      timers.current.push(window.setTimeout(step, 320));
    };
    timers.current.push(window.setTimeout(step, 350));
  }

  function newRound() {
    setPhase("betting");
    setBet(null);
    setSelectedSide(null);
    setShowChipMenu(false);
    setResult(null);
    setMiddle(null);
    setAndar([]);
    setBahar([]);
  }

  function adjustStake(delta: number) {
    setStake((s) => Math.max(STAKE_STEP, Math.min(balance, s + delta)));
  }

  if (portraitPhone) {
    return (
      <div className="rotate-block">
        <span className="rotate-icon">🔄</span>
        <p className="rotate-title">Please rotate your device to landscape mode</p>
        <p className="rotate-sub">Andar Bahar plays best in landscape.</p>
      </div>
    );
  }

  if (screen === "settings") return (
    <div className="app"><Settings onBack={() => setScreen("game")} /></div>
  );

  if (screen === "lobby") return (
    <div className="app">
      <Lobby
        serverUrl={serverUrl}
        onBack={() => setScreen("game")}
        onJoin={(id, tier, mode) => { setOnlineTable({ id, tier, mode }); setScreen("online-table"); }}
      />
    </div>
  );

  if (screen === "online-table" && onlineTable) return (
    <OnlineTable
      serverUrl={serverUrl}
      tableId={onlineTable.id}
      tier={onlineTable.tier}
      mode={onlineTable.mode}
      onLeave={() => { setOnlineTable(null); setScreen("lobby"); }}
    />
  );

  const canConfirm = phase === "betting" && selectedSide !== null && stake <= balance;

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <button className="iconbtn" onClick={() => setConfirmLeave(true)}>←</button>
          <span className="brand"><small>♠♣</small> ANDAR BAHAR <small>♣♠</small></span>
        </div>
        <div className="header-right">
          <span className="balance"><small>₹</small> {balance}</span>
          <span className="live-badge">● LIVE</span>
          <span className={`timer-box${phase === "betting" && timeLeft <= 5 ? " warn" : ""}`}>
            <small>BETTING TIME</small>
            {phase === "betting" ? String(timeLeft).padStart(2, "0") + "s" : "--"}
          </span>
          <button className="iconbtn" aria-pressed={soundOn} onClick={() => setSoundOn((v) => !v)}>
            {soundOn ? "🔊" : "🔇"}
          </button>
          {serverUrl && (
            <button className="iconbtn" title="Play online" onClick={() => setScreen("lobby")}>🌐</button>
          )}
          <button className="iconbtn" onClick={() => setScreen("settings")}>⚙</button>
        </div>
      </header>

      <div className="rail">
        <button className="rail-btn" onClick={() => setRulesPopup("how")}>
          <span className="rail-icon">📖</span>How to Play
        </button>
        <button className="rail-btn" onClick={() => setRulesPopup("rules")}>
          <span className="rail-icon">📜</span>Rules
        </button>
        <button className="rail-btn" onClick={() => setShowHistory((v) => !v)}>
          <span className="rail-icon">🕘</span>History
        </button>
      </div>

      <div className="table-wrap">
        <div className="table-oval">
          <div className={`side-col andar${phase === "result" && result?.won && bet === "andar" ? " win" : ""}`}>
            <span className="side-name andar">ANDAR</span>
            <span className="side-count">{andar.length} card{andar.length === 1 ? "" : "s"}</span>
            <div className="pile">
              {andar.map((c, idx) => <CardView key={idx} card={c} />)}
            </div>
          </div>

          <div className="middle-wrap">
            <span className="middle-label">Open Card</span>
            {middle ? <CardView card={middle} /> : <div className="card-back" />}
            {middle && <span className="target-rank">TARGET RANK: {rankLabel(middle.rank)}</span>}
          </div>

          <div className={`side-col bahar${phase === "result" && result?.won && bet === "bahar" ? " win" : ""}`}>
            <span className="side-name bahar">BAHAR</span>
            <span className="side-count">{bahar.length} card{bahar.length === 1 ? "" : "s"}</span>
            <div className="pile">
              {bahar.map((c, idx) => <CardView key={idx} card={c} />)}
            </div>
          </div>
        </div>
        <div className={`result ${result ? (result.won ? "win" : "lose") : ""}`}>
          {result?.text ?? (phase === "dealing" || phase === "closed" ? "Dealing…" : "")}
        </div>
      </div>

      {showHistory && <div className="history-backdrop" onClick={() => setShowHistory(false)} />}
      <div className={`history-drawer${showHistory ? " open" : ""}`}>
        <HistoryPanel entries={history} onClose={() => setShowHistory(false)} />
      </div>

      <footer className="app-footer">
        <div className="bet-row">
          <div className="chip-group">
            <span className="group-label">Choose Bet Amount</span>
            <div className="chip-select-wrap">
              <button className="chip-select" disabled={phase !== "betting"}
                      onClick={() => setShowChipMenu((v) => !v)}>
                ₹{stake} <span className="chip-select-caret">▾</span>
              </button>
              {showChipMenu && (
                <>
                  <div className="chip-menu-backdrop" onClick={() => setShowChipMenu(false)} />
                  <div className="chip-menu">
                    {CHIPS.map((c) => (
                      <button key={c} className={`chip-menu-item${stake === c ? " active" : ""}`}
                              onClick={() => { setStake(c); setShowChipMenu(false); }}>
                        ₹{c}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="stake-group">
            <span className="group-label">Bet Amount</span>
            <div className="bet-stepper">
              <button disabled={phase !== "betting"} onClick={() => adjustStake(-STAKE_STEP)}>−</button>
              <span>₹{stake}</span>
              <button disabled={phase !== "betting"} onClick={() => adjustStake(STAKE_STEP)}>+</button>
            </div>
          </div>

          <button
            className={`bet andar${selectedSide === "andar" ? " selected" : ""}`}
            disabled={phase !== "betting"}
            onClick={() => setSelectedSide((s) => (s === "andar" ? null : "andar"))}
          >
            ANDAR<small>pays {PAYOUT.andar}×</small>
          </button>
          <button
            className={`bet bahar${selectedSide === "bahar" ? " selected" : ""}`}
            disabled={phase !== "betting"}
            onClick={() => setSelectedSide((s) => (s === "bahar" ? null : "bahar"))}
          >
            BAHAR<small>pays {PAYOUT.bahar}×</small>
          </button>
          <button className="confirm-bet" disabled={!canConfirm} onClick={() => selectedSide && placeBet(selectedSide)}>
            Confirm Bet
          </button>
        </div>

        <p className="hint">
          {stake > balance ? "Not enough balance — lower your stake." :
            serverUrl ? "Online mode: bets settle on your server." :
            "Offline mode: provably-fair local play. Set a server URL in ⚙ for real-money."}
        </p>

        <div className="progress-row">
          <ProgressStepper phase={phase} />
          <button className="action new-round" disabled={phase !== "result"} onClick={newRound}>
            ⟳ New Round
          </button>
        </div>

        {!serverUrl && balance < STAKE_STEP && (phase === "betting" || phase === "result") && (
          <button className="action secondary" onClick={() => updateBalance(1000)}>
            Reset chips to ₹1000 (offline)
          </button>
        )}
      </footer>

      {rulesPopup && (
        <div className="popup-overlay" onClick={() => setRulesPopup(null)}>
          <div className="popup-card" onClick={(e) => e.stopPropagation()}>
            <div className="popup-head">
              <span>{RULES_COPY[rulesPopup].title}</span>
              <button className="iconbtn" onClick={() => setRulesPopup(null)}>✕</button>
            </div>
            <ul className="rules-list">
              {RULES_COPY[rulesPopup].items.map((line, idx) => <li key={idx}>{line}</li>)}
            </ul>
          </div>
        </div>
      )}

      {confirmLeave && (
        <div className="popup-overlay" onClick={() => setConfirmLeave(false)}>
          <div className="popup-card" onClick={(e) => e.stopPropagation()}>
            <div className="popup-head"><span>Leave Table</span></div>
            <p style={{ fontSize: 13, marginBottom: 12 }}>Are you sure you want to leave the table?</p>
            <div className="row">
              <button className="action secondary" style={{ flex: 1 }} onClick={() => setConfirmLeave(false)}>No</button>
              <button className="action" style={{ flex: 1 }} onClick={() => { setConfirmLeave(false); setScreen("lobby"); }}>Yes</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
