# Database assets

- `seeds/` — idempotent seed scripts for local/dev (e.g. a couple of demo tables).
- `fixtures/` — static JSON/CSV fixtures used by tests or manual QA.

The authoritative schema lives in Alembic migrations under
`rummy/backend/alembic/versions`. Create the schema with `alembic upgrade head`.
