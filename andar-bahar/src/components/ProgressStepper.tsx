type Phase = "betting" | "closed" | "dealing" | "result";

const STEPS: { key: Phase; icon: string; label: string; sub: string }[] = [
  { key: "betting", icon: "🪙", label: "Betting", sub: "Place your bet" },
  { key: "closed", icon: "🂡", label: "Open Card", sub: "Card is revealed" },
  { key: "dealing", icon: "🂠", label: "Dealing", sub: "Cards are dealt" },
  { key: "result", icon: "🏆", label: "Result", sub: "Win or lose" },
];

export function ProgressStepper({ phase }: { phase: Phase }) {
  const activeIdx = STEPS.findIndex((s) => s.key === phase);
  return (
    <div className="progress-strip">
      {STEPS.map((s, idx) => (
        <div key={s.key} className="progress-step-wrap">
          <div className={`progress-step${idx === activeIdx ? " active" : ""}${idx < activeIdx ? " done" : ""}`}>
            <span className="progress-icon">{s.icon}</span>
            <span className="progress-text">
              <span className="progress-label">{s.label}</span>
              <span className="progress-sub">{s.sub}</span>
            </span>
          </div>
          {idx < STEPS.length - 1 && <span className="progress-arrow">→</span>}
        </div>
      ))}
    </div>
  );
}
