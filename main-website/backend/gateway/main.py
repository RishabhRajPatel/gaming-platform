"""Public API gateway for the gaming platform.

Routes traffic to the individual game backends and centralises cross-cutting concerns
(auth termination, CORS, rate limiting). This is a thin skeleton: the game logic itself
lives in each game's own service (see ../../../rummy/backend).

Run: uvicorn main:app --port 8080
"""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Platform Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Map a public path prefix to the upstream game service base URL.
SERVICES = {
    "rummy": os.getenv("RUMMY_BACKEND_URL", "http://localhost:8000"),
    # "poker": os.getenv("POKER_BACKEND_URL", "http://localhost:8001"),  # added later
}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "services": list(SERVICES)}


@app.api_route("/{game}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(game: str, path: str, request: Request) -> Response:
    upstream = SERVICES.get(game)
    if upstream is None:
        return Response(content=f'{{"detail":"unknown game {game}"}}',
                        media_type="application/json", status_code=404)
    url = f"{upstream}/{path}"
    async with httpx.AsyncClient() as client:
        proxied = await client.request(
            request.method,
            url,
            params=request.query_params,
            headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
            content=await request.body(),
        )
    return Response(
        content=proxied.content,
        status_code=proxied.status_code,
        media_type=proxied.headers.get("content-type"),
    )
