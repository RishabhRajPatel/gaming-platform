# Security & Compliance

## Reporting
Email security@yourdomain.example. Do not open public issues for vulnerabilities.

## Real-money gaming controls (must be in place before production)
- **Server-authoritative game state.** Clients never compute results; the backend
  engine is the single source of truth. A client only sends intents (draw/discard/declare).
- **Card secrecy.** A player receives only their own hand over the socket. Opponent
  hands and the deck are never serialized to a client until a valid show.
- **RNG.** Shuffle uses a CSPRNG (`secrets`/`random.SystemRandom`), seeded per deal and
  logged (seed stored server-side only) for dispute resolution.
- **Money integrity.** All balances in integer paise. Every wallet mutation is an
  append-only ledger entry with an idempotency key. Deposits/withdrawals reconcile
  against Razorpay via signed webhooks.
- **Webhook verification.** Razorpay webhooks are rejected unless the
  `X-Razorpay-Signature` HMAC-SHA256 matches `RAZORPAY_WEBHOOK_SECRET`.
- **AuthZ.** JWT access tokens; a socket must present a valid token and be a seated
  member of the table to receive/act on that table's events.
- **Anti-collusion & fair play.** Turn timers, action-rate limits, seat/IP heuristics,
  and full action audit logs per round.

## Regulatory checklist (jurisdiction dependent)
- 18+ age gate and KYC before real-money play.
- State-level geo-restrictions where real-money games are prohibited.
- GST / TDS handling on deposits/winnings per local law.
- Responsible-play: deposit limits, self-exclusion, session reminders.

> This file is a checklist, not legal advice. Obtain qualified counsel per jurisdiction.
