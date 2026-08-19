# Deployment

## Local (Docker Compose)
```bash
cp .env.example .env        # fill secrets (SECRET_KEY, Razorpay keys)
docker compose up -d        # postgres + redis + rummy-backend (runs migrations)
cd rummy/frontend && npm install && npm run dev
```
- API: http://localhost:8000  (docs at /docs)
- Frontend: http://localhost:5173

## Local (without Docker)
```bash
# backend
cd rummy/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# frontend (new shell)
cd rummy/frontend && npm install && npm run dev
```

## Migrations
```bash
cd rummy/backend
alembic revision --autogenerate -m "describe change"   # after editing models
alembic upgrade head
```

## Production checklist
- Strong `SECRET_KEY` (32+ bytes) and rotated Razorpay keys in a secret manager.
- Terminate TLS at the edge; run uvicorn behind gunicorn/uvicorn workers or an ASGI
  server manager; put the SPA behind a CDN.
- Managed PostgreSQL with backups + PITR; managed Redis.
- Configure the Razorpay **webhook** URL to `/api/v1/payments/webhook` and set
  `RAZORPAY_WEBHOOK_SECRET`.
- Turn on the compliance controls in `SECURITY.md` before enabling real money
  (`REAL_MONEY_ENABLED=true`): 18+/KYC, geo-restrictions, GST/TDS, responsible play.
- Scale WebSockets with sticky sessions or a Redis-backed table-ownership scheme.

## Environments
`APP_ENV=development|production`. Keep `REAL_MONEY_ENABLED=false` in dev/CI so payment
paths short-circuit safely.
