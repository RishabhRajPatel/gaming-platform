# Contributing

## Branching
- `main` — production, protected. Merge only via reviewed PR with green CI.
- `develop` — integration branch.
- Feature branches: `feat/<scope>-<short-desc>`, fixes: `fix/<scope>-<short-desc>`.
  Scope is the module: `rummy-backend`, `rummy-frontend`, `website`, `infra`.

## Commit style
Conventional Commits: `feat(rummy-backend): add joker validation`.

## Before you push
Backend:
```bash
cd rummy/backend
ruff check app tests
pytest -q
```
Frontend:
```bash
cd rummy/frontend
npm run lint && npm run build
```

## Ground rules
- The **game engine** (`app/game_engine/`) must stay pure Python with **no** framework,
  DB, or network imports. All money/state effects happen in `services/`, never in rules.
- Every rules change ships with a unit test in `tests/`.
- Never commit secrets. Use `.env` (gitignored); update `.env.example` when adding keys.
- Money math uses integer paise (never floats). See `services/wallet.py`.
