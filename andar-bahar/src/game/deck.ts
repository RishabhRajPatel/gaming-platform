export type Suit = "S" | "H" | "D" | "C";
export interface Card {
  rank: number; // 1..13 (A=1, J=11, Q=12, K=13)
  suit: Suit;
}

export const SUITS: Suit[] = ["S", "H", "D", "C"];

export function isRed(suit: Suit): boolean {
  return suit === "H" || suit === "D";
}

export function rankLabel(rank: number): string {
  return { 1: "A", 11: "J", 12: "Q", 13: "K" }[rank] ?? String(rank);
}

export function suitGlyph(suit: Suit): string {
  return { S: "♠", H: "♥", D: "♦", C: "♣" }[suit];
}

export function cardLabel(c: Card): string {
  return `${rankLabel(c.rank)}${suitGlyph(c.suit)}`;
}

export function freshDeck(): Card[] {
  const deck: Card[] = [];
  for (const suit of SUITS) {
    for (let rank = 1; rank <= 13; rank++) deck.push({ rank, suit });
  }
  return deck;
}
