import { X } from "lucide-react";

interface Props {
  onClose: () => void;
}

interface Section {
  title: string;
  body: string;
  example?: string;
  exampleGood?: boolean;
}

// Mirrors exactly what the backend enforces (melds.py / scoring.py / deals_rummy.py) —
// nothing here is aspirational, every rule below is already validated server-side.
const SECTIONS: Section[] = [
  {
    title: "Objective",
    body:
      "Arrange all 13 cards into valid sequences and sets, then Declare. The server " +
      "validates every declaration — the frontend never decides who wins.",
  },
  {
    title: "Deck & Wild Joker",
    body:
      "2 decks + 2 printed jokers are shuffled server-side. One card is cut to set the " +
      "wild rank for the deal — every card of that rank becomes a joker too, on top of " +
      "the 2 printed jokers. A new wild rank is cut for every deal.",
    example: "Cut card: 7♥  →  all four 7s (7♥ 7♠ 7♦ 7♣) are wild this deal, plus both printed jokers.",
  },
  {
    title: "Pure Sequence",
    body: "3+ consecutive cards, same suit, with no joker substituted anywhere in it.",
    example: "4♥ 5♥ 6♥",
    exampleGood: true,
  },
  {
    title: "Impure Sequence",
    body: "3+ consecutive cards, same suit, where a joker fills one or more gaps.",
    example: "4♥ 5♥ [wild→6♥] 7♥",
    exampleGood: true,
  },
  {
    title: "Set",
    body: "3 or 4 cards of the same rank, each a different suit. A joker can fill a missing suit.",
    example: "K♥ K♠ K♦   or   K♥ K♠ [joker→K♦]",
    exampleGood: true,
  },
  {
    title: "Invalid Group",
    body: "Anything that isn't a pure sequence, impure sequence, or set.",
    example: "5♣ 7♠ J♣  →  no run, no matching rank",
    exampleGood: false,
  },
  {
    title: "Minimum to Declare",
    body:
      "All 13 cards grouped, at least 2 sequences total, and at least 1 of those must be " +
      "pure. Missing the pure sequence invalidates the whole declaration, even if every " +
      "other group is perfect.",
    example: "2♠ 3♠ 4♠ (pure) + 7♥ 8♥ [J]9♥ (impure) + K♥ K♠ K♦ (set) + 5♣ 6♣ 7♣ 8♣ (pure) = 13 ✅",
    exampleGood: true,
  },
  {
    title: "Scoring (deadwood)",
    body:
      "A, J, Q, K each count 10. Number cards count their face value. Cards in a valid " +
      "group score 0 — only ungrouped cards count against you, capped at 80 points.",
    example: "Ungrouped 5♣ 7♠ J♣  →  5 + 7 + 10 = 22 points",
  },
  {
    title: "Turn",
    body:
      "Draw exactly one card (from the closed deck or the open discard pile), optionally " +
      "arrange, then discard exactly one card. You cannot draw twice or discard before " +
      "drawing — the server rejects out-of-order or out-of-turn actions.",
  },
  {
    title: "Drop",
    body:
      "Leave the current deal without declaring. Dropping before you've drawn on your " +
      "first turn costs less than dropping mid-deal.",
    example: "First drop = 20 points   ·   Middle drop = 40 points",
  },
  {
    title: "Invalid Declare",
    body:
      "Declaring a hand that fails validation costs the full 80-point penalty and ends " +
      "your deal immediately — arrange carefully before declaring.",
  },
  {
    title: "Turn Timer",
    body:
      "Each turn has a time limit (default 30s), enforced by the server, not the browser. " +
      "If time runs out, the server auto-plays your turn for you so the game never stalls.",
  },
];

export default function RulesModal({ onClose }: Props) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="card-surface w-full max-w-lg max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-ink-700">
          <h2 className="font-display text-lg font-bold text-gold-400">📖 How to Play — Rules</h2>
          <button className="btn-ghost p-1.5 rounded-full" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4 space-y-4">
          {SECTIONS.map((s) => (
            <div key={s.title}>
              <h3 className="text-sm font-semibold text-gold-400 mb-1">{s.title}</h3>
              <p className="text-sm text-slate-300 leading-relaxed">{s.body}</p>
              {s.example && (
                <p
                  className={`mt-1.5 text-xs font-mono px-2.5 py-1.5 rounded-lg inline-block ${
                    s.exampleGood === false
                      ? "bg-red-900/30 text-red-300 border border-red-800"
                      : "bg-ink-800 text-slate-200 border border-ink-700"
                  }`}
                >
                  {s.example}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
