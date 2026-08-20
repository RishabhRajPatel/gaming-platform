from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class BetRequest(BaseModel):
    bet: Literal["andar", "bahar"]
    stake: int = Field(gt=0, description="Stake in chips (virtual) or paise (real)")
    client_seed: str = Field(min_length=1, max_length=120)
    nonce: int = Field(ge=0)
    mode: Literal["virtual", "real"] = "virtual"


class BetResponse(BaseModel):
    round: dict
    settlement: dict
    balance: int
    server_seed: str
    server_seed_hash: str


# ---- Real-time table (WebSocket) --------------------------------------------------------

class TableCreate(BaseModel):
    name: str = "Andar Bahar"
    mode: Literal["virtual", "real"] = "virtual"
    max_players: int = Field(default=8, ge=1, le=50)
    betting_seconds: int = Field(default=15, ge=10, le=60)
    is_private: bool = False


class TableOut(BaseModel):
    id: str
    name: str
    mode: str
    status: str
    max_players: int
    betting_seconds: int
    online_players: int = 0
    is_private: bool = False
    join_code: Optional[str] = None

    model_config = {"from_attributes": True}


# ---- WebSocket message payload (client -> server) ----------------------------------------
class WSAction(BaseModel):
    action: str  # bet | sync
    side: Optional[Literal["andar", "bahar"]] = None
    stake: Optional[int] = None
