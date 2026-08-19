# Architecture

## Big picture
```
              ┌─────────────┐        REST (/api/v1/*)        ┌──────────────────────┐
  Browser ───▶│  React SPA  │ ─────────────────────────────▶│  FastAPI (rummy)     │
  (player)    │  (Vite/TS)  │ ─── WebSocket (/ws/game/:id) ─▶│  ┌────────────────┐  │
              └─────────────┘                                │  │ game_engine    │  │
                                                             │  │ (pure Python)  │  │
                                                             │  └────────────────┘  │
                                                             │  services / models   │
                                                             └──────────┬───────────┘
                                                                        │
                                                       ┌────────────────┼─────────────┐
                                                       ▼                ▼             ▼
                                                  PostgreSQL          Redis        Razorpay
                                                 (users, wallet,   (ws pub/sub,   (deposits,
                                                  ledger, games)     turn state)   webhooks)
```

## Layers (rummy backend)
1. **Transport** — `routers/` (REST) and `websocket/` (real-time). No game rules here.
2. **Services** — `services/` orchestrate: wallet ledger, Razorpay, game manager.
3. **Engine** — `game_engine/` is pure, deterministic, framework-free rummy rules. It is
   the single source of truth for game outcomes and is fully unit-tested.
4. **Persistence** — `models/` (SQLAlchemy) + Alembic migrations.

## Why the engine is isolated
Keeping rules in a dependency-free package means: (a) they're trivially unit-testable,
(b) the same code can power a bot, a replay/audit tool, and the live server, and (c) money
and state effects can never leak into rule evaluation.

## Real-time model
The server holds authoritative game state (`services/game_manager`). Clients send intents
over the socket (`draw`/`discard`/`declare`/`drop`); the server validates against the
engine, mutates state, then broadcasts the redacted public state to everyone and each
player's private hand only to them. Turn timers auto-play missed turns.

## Scaling out
For multiple workers, make one process the owner of each table and fan state changes
through Redis pub/sub; the `GameManager` becomes the owning worker's local cache. The
engine's `public_state()` + per-player hands are already serialisable.

## Adding a new game (e.g. poker, later)
Add a sibling `poker/` module with its own engine + backend, and register it in the
`main-website/backend/gateway`. Nothing in `rummy/` needs to change.
