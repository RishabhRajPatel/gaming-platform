# Deals Rummy — Rules as Implemented

This is the exact ruleset the engine in `rummy/backend/app/game_engine/` enforces.

## Format
- **Players:** 2 to 4 at a table.
- **Deals:** a fixed number per game (configurable, default 2). Everyone starts with an
  equal chip stack. After the last deal, the player with the **most chips wins**.
- **Cards:** two standard 52-card decks + 2 printed jokers (106-card shoe). Each player
  is dealt **13 cards**.

## The wild joker
At the start of each deal one card is cut as the **wild joker**. Every card of that rank
(all four suits, both decks) becomes wild for the deal, alongside the two printed jokers.
If the cut card is itself a printed joker, Aces are wild by convention.

## Melds
To win you arrange all 13 cards into valid melds:

- **Pure sequence** — 3+ cards, same suit, consecutive, **with no joker of any kind**.
- **Impure sequence** — 3+ cards, same suit, consecutive, with one or more jokers filling
  gaps.
- **Set** — 3 or 4 cards of the **same rank**, all **different suits** (jokers may
  substitute). Never more than 4, never two of the same suit.
- Ace is low (A-2-3) or high (Q-K-A). **K-A-2 wrap-around is not allowed.**

## Winning a deal (a valid declaration)
A declaration is valid only if **all 13 cards** form valid melds **and**:
1. there are **at least two sequences**, and
2. **at least one** of them is a **pure** sequence.

An invalid declaration ("wrong show") costs the full **80** points and the player is out
of that deal.

## Turn flow
On your turn you **draw** one card (from the closed stock or the open discard pile), then
**discard** one card. To finish, draw, arrange, and declare, discarding your 14th card.

## Dropping
- **First drop** (before you draw on your first turn): **20** points.
- **Middle drop** (any later turn): **40** points.
A dropped player is out of the deal but stays in the game for remaining deals.

## Scoring a deal
- The winner scores **0**.
- Each opponent's score = their **deadwood** points. Card points: A, J, Q, K = 10;
  numbers = face value; jokers = 0. A hand is capped at **80**.
- **Crucial rule:** you may only deduct melds if you hold **at least one pure sequence**.
  With no pure sequence, your **entire hand** counts (capped at 80). The engine
  auto-arranges a losing hand to its lowest legal score (`best_hand_score`).

## Chips settlement (zero-sum)
At the end of each deal the winner **gains** chips equal to the sum of all opponents'
points; each opponent **loses** chips equal to their own points. Totals are conserved.

## Fair play
Shuffles use a cryptographically-secure RNG; the per-deal seed is stored server-side for
dispute resolution. The server is authoritative — a client only ever sends intents and
only ever sees its own hand.
