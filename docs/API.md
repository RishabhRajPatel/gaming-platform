# API Reference (rummy backend)

Base URL: `/api/v1`. Auth: `Authorization: Bearer <jwt>` (from `/auth/login`).
Interactive docs are served at `/docs` (Swagger) when the backend is running.

## Auth
| Method | Path             | Body                                        | Notes            |
|--------|------------------|---------------------------------------------|------------------|
| POST   | `/auth/register` | email, username, password, is_18_plus       | 201, creates wallet |
| POST   | `/auth/login`    | email, password                             | → `access_token` |
| GET    | `/auth/me`       | —                                           | current user     |

## Wallet
| Method | Path                    | Notes                          |
|--------|-------------------------|--------------------------------|
| GET    | `/wallet`               | balances (real/bonus/virtual)  |
| GET    | `/wallet/transactions`  | ledger, newest first           |

## Payments (Razorpay)
| Method | Path                  | Notes                                             |
|--------|-----------------------|---------------------------------------------------|
| POST   | `/payments/deposit`   | 18+ & real-money gated; returns a Razorpay order  |
| POST   | `/payments/webhook`   | Razorpay → us; signature-verified; credits wallet |

## Tables
| Method | Path              | Notes                                  |
|--------|-------------------|----------------------------------------|
| GET    | `/tables`         | list open tables                        |
| POST   | `/tables`         | create (mode `free`/`real_money`)       |
| GET    | `/tables/{id}`    | table detail                            |

## Health
`GET /health` → `{"status":"ok"}`

## WebSocket — real-time game
Connect: `ws://<host>/ws/game/{table_id}?token=<jwt>`

**Client → server**
```json
{"action": "join"}
{"action": "start"}
{"action": "draw", "source": "stock"}     // or "discard"
{"action": "discard", "card": "5S0"}
{"action": "declare", "groups": [["4S0","5S0","6S0"], ...]}
{"action": "drop"}
{"action": "sync"}
```

**Server → client**
```json
{"type": "state", "state": { /* public table state */ }}
{"type": "hand", "cards": ["5S0","KH1", ...]}   // your private hand only
{"type": "event", "event": "deal_started" | "declared" | "deal_over" | "game_over" | "turn_timeout"}
{"type": "error", "message": "it is <player>'s turn"}
```
Card codes are `"<rank><suit><deckIndex>"` (e.g. `KH0`, `10S1`) or `"PJ0"` for a printed joker.
