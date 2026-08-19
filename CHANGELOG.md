# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]
### Added
- Monorepo scaffold (rummy + main-website; poker intentionally excluded for now).
- Pure-Python **Deals Rummy** game engine: 2-deck shoe, jokers, pure/impure sequence
  and set validation, hand scoring, and Deals-format flow (2–4 players, configurable deals).
- FastAPI backend scaffold: config, security, models, schemas, services, routers, health.
- WebSocket real-time game layer (connection/table managers, event protocol, turn timers).
- Wallet service with append-only ledger and **Razorpay** order + webhook integration.
- React + Vite + TypeScript + Tailwind frontend scaffold with dark premium theme.
- Docker Compose (Postgres + Redis + backend) and GitHub Actions CI.
