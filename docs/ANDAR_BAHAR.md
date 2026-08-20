# Andar Bahar — Game, App & Backend

A second game in the platform: **Andar Bahar**, shipped as an installable **Android app**
(Capacitor) backed by the same FastAPI + PostgreSQL platform.

## Pieces
- **Mobile app** — `andar-bahar/` (React + Vite + TS + Capacitor). Offline provably-fair
  play with virtual chips, or online real-money play against the backend. Build the APK
  via the `Andar Bahar APK` GitHub Actions workflow or locally with Gradle
  (`andar-bahar/README.md`).
- **Engine** — `rummy/backend/app/andar_bahar/engine.py` (pure Python, server-authoritative,
  provably fair) and a mirrored TS engine in `andar-bahar/src/game/` for offline play.
- **API** — `POST /api/v1/andar-bahar/bet` settles a bet against the player's wallet.

## Rules
One 52-card deck is shuffled; the top card is the **middle** card. A **black** middle
card (♠/♣) starts dealing on **Andar**, a **red** one (♥/♦) on **Bahar**. Cards are dealt
alternately from the start side until a card of the **middle's rank** appears — that side
wins. Players bet Andar or Bahar. Payouts: **Andar 0.9×, Bahar 1.0×** (net).

## Provable fairness
Per bet the server generates a secret `server_seed` and derives the shuffle seed as
`HMAC_SHA256(server_seed, "client_seed:nonce")`. The response returns both the
`server_seed` and its `sha256` hash so a player can reproduce the exact deal and verify it
wasn't tampered with. `(client_seed, nonce)` also makes each bet idempotent — a retry
replays the stored round instead of dealing again or double-charging.

## Wallet & money
Virtual mode uses `virtual_chips` (new players get a one-time 1000-chip welcome grant).
Real mode uses `real_paise` and is gated behind 18+ and `REAL_MONEY_ENABLED`. All wallet
moves are integer-amount, idempotent ledger entries — same guarantees as the rummy wallet.

## Bet endpoint
```
POST /api/v1/andar-bahar/bet     (Authorization: Bearer <jwt>)
{ "bet": "andar|bahar", "stake": 50, "client_seed": "abc", "nonce": 1, "mode": "virtual|real" }
→ { round, settlement, balance, server_seed, server_seed_hash }
```
