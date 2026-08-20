import { cardLabel } from "../game/deck";
import type { HistoryEntry } from "../services/config";

export function HistoryPanel({ entries, onClose }: { entries: HistoryEntry[]; onClose?: () => void }) {
  return (
    <div className="history-sidebar">
      <div className="history-title-row">
        <span className="history-title">Round History</span>
        {onClose && <button className="history-close" onClick={onClose}>✕</button>}
      </div>
      {entries.length === 0 ? (
        <div className="history-empty">No rounds yet.</div>
      ) : (
        <div className="history-table">
          <div className="history-row history-head">
            <span>#</span>
            <span>Open Card</span>
            <span>Result</span>
            <span>Bet</span>
            <span>Win/Loss</span>
          </div>
          <div className="history-body">
            {entries.map((e, idx) => (
              <div key={e.id} className={`history-row ${e.won ? "win" : "lose"}`}>
                <span className="history-num">{entries.length - idx}</span>
                <span className="history-open">{cardLabel(e.openCard)}</span>
                <span className={`history-result ${e.winner}`}>
                  {e.winner === "andar" ? "Andar" : "Bahar"}
                </span>
                <span className="history-stake">₹{e.stake}</span>
                <span className="history-outcome">{e.won ? `+₹${e.payout}` : `−₹${e.stake}`}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
