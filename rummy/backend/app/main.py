"""FastAPI application entrypoint for the Deals Rummy backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import auth, health, payments, tables, wallet
from app.websocket import game_ws, matchmaking_ws

app = FastAPI(
    title="Deals Rummy API",
    version="0.1.0",
    description="Real-money Deals Rummy (2–4 players) with real-time WebSocket play.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
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

# WebSocket (no version prefix)
app.include_router(game_ws.router)
app.include_router(matchmaking_ws.router)


@app.get("/")
def root() -> dict:
    return {"service": "deals-rummy", "docs": "/docs", "health": f"{prefix}/health"}
