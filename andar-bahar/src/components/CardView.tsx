import { Card, isRed, rankLabel, suitGlyph } from "../game/deck";

export function CardView({ card, small }: { card: Card; small?: boolean }) {
  return (
    <div className={`card${small ? " small" : ""}${isRed(card.suit) ? " red" : ""}`}>
      <span className="r">{rankLabel(card.rank)}</span>
      <span className="s">{suitGlyph(card.suit)}</span>
    </div>
  );
}

export function CardBack() {
  return <div className="card-back" />;
}
