"""FastAPI application entrypoint for the Deals Rummy backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.andar_bahar import router as andar_bahar
from app.core.config import settings
from app.routers import auth, health, payments, tables, wallet
from app.teen_patti import router as teen_patti
from app.websocket import andar_bahar_ws, game_ws, matchmaking_ws, teen_patti_ws

app = FastAPI(
    title="Deals Rummy API",
    version="0.1.0",
    description="Real-money Deals Rummy (2–4 players) with real-time WebSocket play.",
)

app.add_middleware(
    CORSMiddleware,
    # `frontend_origin` (the React app) plus the static-HTML games (andar-bahar,
    # teen-patti) opened from a packaged Capacitor app. CORS matches the Origin
    # header exactly including port, so any local dev static-file server
    # (`python -m http.server`, VS Code Live Server, etc.) needs the regex below
    # rather than one hardcoded port.
    allow_origins=[settings.frontend_origin, "capacitor://localhost"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers under /api/v1
prefix = settings.api_v1_prefix
app.include_router(health.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
app.include_router(wallet.router, prefix=prefix)
app.include_router(payments.router, prefix=prefix)
app.include_router(tables.router, prefix=prefix)
app.include_router(andar_bahar.router, prefix=prefix)
app.include_router(teen_patti.router, prefix=prefix)

# WebSocket (no version prefix)
app.include_router(game_ws.router)
app.include_router(matchmaking_ws.router)
app.include_router(teen_patti_ws.router)
app.include_router(andar_bahar_ws.router)


@app.get("/")
def root() -> dict:
    return {"service": "deals-rummy", "docs": "/docs", "health": f"{prefix}/health"}
