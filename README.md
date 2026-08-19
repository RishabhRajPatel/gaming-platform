# Gaming Platform — Deals Rummy

A production-grade, real-money **Deals Rummy** platform (2–4 players) with real-time
multiplayer over WebSockets. Built as a monorepo so additional games (e.g. Poker) can
be added later as sibling modules without touching the core.

> **Status:** Rummy is the active module. Poker is intentionally **not** built here —
> it will be added later by a separate track. The shared `main-website` module handles
> auth, user profiles and the API gateway that fronts every game.

## Monorepo layout

```
gaming-platform/
├── rummy/                 # Deals Rummy — the live game
│   ├── backend/           # FastAPI + WebSocket game server + Razorpay wallet
│   │   └── app/
│   │       ├── game_engine/   # Pure, framework-free Deals Rummy rules engine
│   │       ├── websocket/     # Real-time table/room protocol
│   │       ├── routers/       # REST API
│   │       ├── models/        # SQLAlchemy models
│   │       ├── schemas/       # Pydantic schemas
│   │       ├── services/      # Wallet, Razorpay, matchmaking, game orchestration
│   │       ├── db/            # Session, base
│   │       └── core/          # Config, security, logging
│   └── frontend/          # React + Vite + TypeScript + Tailwind (dark premium theme)
│
├── main-website/          # Shared platform surface
│   ├── backend/           # auth / users / gateway
│   └── frontend/          # home / login / register / profile / lobby
│
├── database/              # Seeds & fixtures
├── docs/                  # Architecture, game rules, API, deployment
├── scripts/               # setup.sh, dev.sh
└── docker-compose.yml     # Postgres + Redis + backend for local dev
```

## Tech stack

| Layer      | Choice                                                    |
|------------|-----------------------------------------------------------|
| Backend    | FastAPI, SQLAlchemy, Alembic, Pydantic v2, Pytest         |
| Real-time  | Native FastAPI WebSockets + Redis pub/sub (horizontal)    |
| Database   | PostgreSQL 16                                             |
| Cache/RT   | Redis 7                                                   |
| Payments   | **Razorpay** (orders + webhook signature verification)    |
| Frontend   | React 18, Vite, TypeScript, Tailwind CSS, Zustand, Axios  |
| Infra      | Docker Compose (dev), GitHub Actions (CI)                 |

## Quick start

```bash
# 1. Copy env and fill secrets
cp .env.example .env

# 2. Bring up Postgres + Redis + backend
docker compose up -d

# 3. Backend (local, without Docker)
cd rummy/backend
python -m venv .venv && .venv\Scripts\Activate  
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 4. Frontend
cd rummy/frontend
npm install
npm run dev
```

Backend health: `GET http://localhost:8000/api/v1/health` → `{"status":"ok"}`
Game WebSocket: `ws://localhost:8000/ws/game/{table_id}?token=...`

## The game engine

The Deals Rummy rules live in [`rummy/backend/app/game_engine/`](rummy/backend/app/game_engine/)
and depend on **nothing** but the Python standard library. That means the rules are
unit-testable in isolation and can be reused by a bot/AI, a replay tool, or a second
transport. See [`docs/GAME_RULES.md`](docs/GAME_RULES.md) for the exact rules implemented.

## Responsible / legal note

Real-money skill gaming is regulated and taxed differently across Indian states and other
jurisdictions. Before going live you are responsible for KYC, age-gating (18+), state
geo-restrictions, GST/TDS handling, and a responsible-play program. See
[`SECURITY.md`](SECURITY.md) and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## License

See [`LICENSE`](LICENSE).
