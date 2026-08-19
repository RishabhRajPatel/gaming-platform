# Database

PostgreSQL 16. Schema is managed by Alembic (`rummy/backend/alembic`).

## Tables
- **users** — identity, role, 18+/KYC status.
- **wallets** — one per user; integer paise for `real`/`bonus`, integer `virtual_chips`.
- **wallet_transactions** — append-only ledger; every mutation has an `idempotency_key`
  and records `balance_after`. Money is never stored as a float.
- **game_tables** — table config (mode, deals, entry fee, seats, timers).
- **game_rounds** — finished game results + seeds for replay/audit.
- **deposits** / **withdrawals** — Razorpay order + payout lifecycle.
- **audit_logs** — append-only security/game/money event trail.

## Money integrity
All amounts are integer **paise** (₹1 = 100 paise). The wallet service
(`services/wallet.py`) is the only writer; it enforces non-negative balances and
idempotency so a webhook or a retried request can never double-credit.

## Seeds & fixtures
`database/seeds/` and `database/fixtures/` hold optional dev data (sample tables/users).
