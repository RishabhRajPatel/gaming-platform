// Client-side mirror of the backend's app/game_engine/melds.py + rank_points, used
// only to color-code groups live as the player arranges their hand. The server
// (declare()) is the sole authority at declaration time — this never blocks an action,
// it's purely visual feedback.

export interface ParsedCard {
  code: string;
  rank: number; // 1 (Ace) .. 13 (King); 0 for printed jokers
  suit: "S" | "H" | "D" | "C" | null;
  printedJoker: boolean;
}

const RANK_LABELS: Record<string, number> = {
  A: 1, J: 11, Q: 12, K: 13,
};

export function parseCard(code: string): ParsedCard {
  if (code.startsWith("PJ")) {
    return { code, rank: 0, suit: null, printedJoker: true };
  }
  // rank label is "10" (2 chars) or a single char; suit is 1 char; deck index is 1 digit.
  const rankLabel = code.length === 4 ? code.slice(0, 2) : code.slice(0, 1);
  const suit = code[rankLabel.length] as ParsedCard["suit"];
  const rank = RANK_LABELS[rankLabel] ?? parseInt(rankLabel, 10);
  return { code, rank, suit, printedJoker: false };
}

export function isWild(card: ParsedCard, wildRank: number | null): boolean {
  if (card.printedJoker) return true;
  return wildRank != null && card.rank === wildRank;
}

export function rankPoints(rank: number): number {
  return rank === 1 || rank >= 11 ? 10 : rank;
}

export function deadwoodPoints(codes: string[], wildRank: number | null): number {
  return codes.reduce((sum, code) => {
    const c = parseCard(code);
    return sum + (isWild(c, wildRank) ? 0 : rankPoints(c.rank));
  }, 0);
}

export type MeldType = "pure_sequence" | "impure_sequence" | "set" | "invalid";

function isConsecutive(sorted: number[]): boolean {
  return sorted.every((r, i) => i === 0 || r - sorted[i - 1] === 1);
}

function naturalsFormRun(cards: ParsedCard[]): boolean {
  if (new Set(cards.map((c) => c.suit)).size !== 1) return false;
  const ranks = cards.map((c) => c.rank).sort((a, b) => a - b);
  if (new Set(ranks).size !== ranks.length) return false;
  if (isConsecutive(ranks)) return true;
  if (ranks.includes(1)) {
    const high = ranks.map((r) => (r === 1 ? 14 : r)).sort((a, b) => a - b);
    if (new Set(high).size === high.length && isConsecutive(high)) return true;
  }
  return false;
}

function isPureSequence(cards: ParsedCard[], wildRank: number | null): boolean {
  if (cards.length < 3) return false;
  if (cards.some((c) => isWild(c, wildRank))) return false;
  return naturalsFormRun(cards);
}

function impureSequenceOk(naturals: ParsedCard[], jokerCount: number): boolean {
  if (naturals.length === 0) return false;
  if (new Set(naturals.map((c) => c.suit)).size !== 1) return false;
  const ranks = naturals.map((c) => c.rank).sort((a, b) => a - b);
  if (new Set(ranks).size !== ranks.length) return false;

  const gapsFillable = (rseq: number[]): boolean => {
    const span = rseq[rseq.length - 1] - rseq[0] + 1;
    const internalMissing = span - rseq.length;
    if (internalMissing < 0 || internalMissing > jokerCount) return false;
    const leftover = jokerCount - internalMissing;
    const totalLen = span + leftover;
    return totalLen >= 3 && totalLen <= 13;
  };

  if (gapsFillable(ranks)) return true;
  if (ranks.includes(1)) {
    const high = ranks.map((r) => (r === 1 ? 14 : r)).sort((a, b) => a - b);
    if (new Set(high).size === high.length && gapsFillable(high)) return true;
  }
  return false;
}

function isSet(cards: ParsedCard[], wildRank: number | null): boolean {
  const n = cards.length;
  if (n < 3 || n > 4) return false;
  const naturals = cards.filter((c) => !isWild(c, wildRank));
  const jokers = n - naturals.length;
  if (naturals.length === 0) return false;
  if (new Set(naturals.map((c) => c.rank)).size !== 1) return false;
  const suits = naturals.map((c) => c.suit);
  if (new Set(suits).size !== suits.length) return false;
  return naturals.length + jokers === n && n <= 4;
}

export function classifyGroup(codes: string[], wildRank: number | null): MeldType {
  if (codes.length < 3) return "invalid";
  const cards = codes.map(parseCard);
  if (isPureSequence(cards, wildRank)) return "pure_sequence";
  const naturals = cards.filter((c) => !isWild(c, wildRank));
  const jokerCount = cards.length - naturals.length;
  if (impureSequenceOk(naturals, jokerCount)) return "impure_sequence";
  if (isSet(cards, wildRank)) return "set";
  return "invalid";
}

function sortKey(c: ParsedCard): [number, string, number] {
  return [c.printedJoker ? 1 : 0, c.suit ?? "~", c.rank];
}

/** Order cards by suit/rank (jokers last) without attempting to group them into melds. */
export function sortHand(codes: string[]): string[] {
  return [...codes]
    .map(parseCard)
    .sort((a, b) => {
      const [aj, as, ar] = sortKey(a);
      const [bj, bs, br] = sortKey(b);
      return aj - bj || as.localeCompare(bs) || ar - br;
    })
    .map((c) => c.code);
}

/**
 * Greedy best-effort grouping into melds (pure sequences, then sets, then
 * joker-filled impure sequences/sets), leaving anything left over as singletons.
 * This is a visual aid only — not guaranteed optimal, unlike the server's scorer.
 */
export function autoArrange(codes: string[], wildRank: number | null): string[][] {
  const all = codes.map(parseCard);
  let jokerPool = all.filter((c) => isWild(c, wildRank)).map((c) => c.code);
  let naturals = all.filter((c) => !isWild(c, wildRank));
  const used = new Set<string>();
  const groups: string[][] = [];

  // Pass 1: pure sequences — maximal consecutive same-suit runs.
  const bySuit: Record<string, ParsedCard[]> = {};
  for (const c of naturals) if (c.suit) (bySuit[c.suit] ??= []).push(c);
  for (const suit of Object.keys(bySuit)) {
    const seenRank = new Set<number>();
    const sorted = [...bySuit[suit]]
      .sort((a, b) => a.rank - b.rank)
      .filter((c) => (seenRank.has(c.rank) ? false : (seenRank.add(c.rank), true)));
    let i = 0;
    while (i < sorted.length) {
      let j = i;
      while (j + 1 < sorted.length && sorted[j + 1].rank === sorted[j].rank + 1) j++;
      if (j - i + 1 >= 3) {
        const group = sorted.slice(i, j + 1).map((c) => c.code);
        group.forEach((c) => used.add(c));
        groups.push(group);
      }
      i = j + 1;
    }
  }
  naturals = naturals.filter((c) => !used.has(c.code));

  // Pass 2: sets — same rank, distinct suits.
  const byRank: Record<number, ParsedCard[]> = {};
  for (const c of naturals) (byRank[c.rank] ??= []).push(c);
  for (const rank of Object.keys(byRank).map(Number)) {
    const seenSuit = new Set<string>();
    const uniq = byRank[rank].filter((c) => {
      if (!c.suit || seenSuit.has(c.suit)) return false;
      seenSuit.add(c.suit);
      return true;
    });
    if (uniq.length >= 3) {
      const group = uniq.slice(0, 4).map((c) => c.code);
      group.forEach((c) => used.add(c));
      groups.push(group);
    }
  }
  naturals = naturals.filter((c) => !used.has(c.code));

  // Pass 3: impure sequences — same-suit chunks with a single joker-fillable gap.
  const bySuit2: Record<string, ParsedCard[]> = {};
  for (const c of naturals) if (c.suit) (bySuit2[c.suit] ??= []).push(c);
  for (const suit of Object.keys(bySuit2)) {
    let sorted = [...bySuit2[suit]].sort((a, b) => a.rank - b.rank);
    let placed = true;
    while (placed && sorted.length >= 2 && jokerPool.length > 0) {
      placed = false;
      for (let start = 0; start < sorted.length && !placed; start++) {
        for (let end = sorted.length - 1; end > start && !placed; end--) {
          const chunk = sorted.slice(start, end + 1);
          const span = chunk[chunk.length - 1].rank - chunk[0].rank + 1;
          const need = span - chunk.length;
          if (need > 0 && need <= jokerPool.length && span >= 3 && span <= 13) {
            const chunkCodes = chunk.map((c) => c.code);
            const usedJokers = jokerPool.slice(0, need);
            jokerPool = jokerPool.slice(need);
            chunkCodes.forEach((c) => used.add(c));
            groups.push([...chunkCodes, ...usedJokers]);
            sorted = sorted.filter((c) => !chunkCodes.includes(c.code));
            placed = true;
          }
        }
      }
    }
  }
  naturals = naturals.filter((c) => !used.has(c.code));

  // Pass 4: impure sets — 1-2 naturals of a rank topped up with jokers.
  const byRank2: Record<number, ParsedCard[]> = {};
  for (const c of naturals) (byRank2[c.rank] ??= []).push(c);
  for (const rank of Object.keys(byRank2).map(Number)) {
    const cardsForRank = byRank2[rank];
    const need = 3 - cardsForRank.length;
    if (cardsForRank.length >= 1 && cardsForRank.length < 3 && jokerPool.length >= need) {
      const usedJokers = jokerPool.slice(0, need);
      jokerPool = jokerPool.slice(need);
      const group = [...cardsForRank.map((c) => c.code), ...usedJokers];
      group.forEach((c) => used.add(c));
      groups.push(group);
    }
  }
  naturals = naturals.filter((c) => !used.has(c.code));

  // Whatever's left is deadwood — one singleton group per card, sorted for readability.
  for (const c of sortHand(naturals.map((c) => c.code))) groups.push([c]);
  for (const j of jokerPool) groups.push([j]);

  return groups;
}
