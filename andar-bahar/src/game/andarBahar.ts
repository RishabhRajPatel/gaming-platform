/**
 * Andar Bahar game engine (pure functions, no UI/network).
 *
 * Rules:
 *  - One 52-card deck is shuffled. The top card is the "joker" (middle card).
 *  - The starting side is decided by the middle card's colour: a black middle card
 *    (♠/♣) starts on ANDAR, a red one (♥/♦) starts on BAHAR. (Common Indian rule.)
 *  - Cards are dealt one at a time, alternating sides starting from the start side,
 *    until a card of the SAME RANK as the middle card appears. That side wins.
 *  - Players bet ANDAR or BAHAR before the deal.
 */
import { Card, freshDeck, isRed } from "./deck";
import { hashSeed, mulberry32, shuffle } from "./rng";

export type Side = "andar" | "bahar";

export interface DealStep {
  side: Side;
  card: Card;
}

export interface RoundResult {
  middle: Card;
  startSide: Side;
  steps: DealStep[];
  andar: Card[];
  bahar: Card[];
  winner: Side;
  cardsDealt: number;
}

export function startSideFor(middle: Card): Side {
  return isRed(middle.suit) ? "bahar" : "andar";
}

/** Play a round from an already-shuffled 52-card deck. */
export function playRoundFromDeck(deck: Card[]): RoundResult {
  const middle = deck[0];
  const rest = deck.slice(1);
  const startSide = startSideFor(middle);

  const andar: Card[] = [];
  const bahar: Card[] = [];
  const steps: DealStep[] = [];

  let side: Side = startSide;
  let winner: Side | null = null;

  for (const card of rest) {
    (side === "andar" ? andar : bahar).push(card);
    steps.push({ side, card });
    if (card.rank === middle.rank) {
      winner = side;
      break;
    }
    side = side === "andar" ? "bahar" : "andar";
  }

  // With a full deck there are always 3 more matching-rank cards, so a winner exists.
  if (winner === null) winner = side;

  return {
    middle,
    startSide,
    steps,
    andar,
    bahar,
    winner,
    cardsDealt: steps.length,
  };
}

/** Deterministic round from a seed string (client seed + nonce) — provably fair. */
export function playRoundFromSeed(seed: string): RoundResult {
  const rng = mulberry32(hashSeed(seed));
  const deck = shuffle(freshDeck(), rng);
  return playRoundFromDeck(deck);
}

// ---- Betting / payouts ---------------------------------------------------------------
// Traditional edge: Andar (which usually receives the first card) pays a touch less.
export const PAYOUT = { andar: 0.9, bahar: 1.0 } as const;

export interface Settlement {
  won: boolean;
  stake: number;
  payout: number; // net winnings (0 if lost)
  returned: number; // total returned to balance (stake + payout if won, else 0)
}

export function settleBet(bet: Side, stake: number, winner: Side): Settlement {
  const won = bet === winner;
  const payout = won ? Math.round(stake * PAYOUT[bet]) : 0;
  return { won, stake, payout, returned: won ? stake + payout : 0 };
}
