from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PlayHandRequest(BaseModel):
    boot: int = Field(default=10, gt=0, le=10_000, description="Entry stake in chips (virtual) or paise (real)")
    client_seed: str = Field(min_length=1, max_length=120)
    nonce: int = Field(ge=0)
    mode: Literal["virtual", "real"] = "virtual"


class PlayHandResponse(BaseModel):
    hand: dict
    settlement: dict
    balance: int
    server_seed: str
    server_seed_hash: str


# ---- Real-time table (WebSocket) --------------------------------------------------------

class TableCreate(BaseModel):
    name: str = "Teen Patti"
    mode: Literal["virtual", "real"] = "virtual"
    max_players: int = Field(default=4, ge=2, le=4)
    boot_amount: int = Field(default=10, gt=0, le=10_000)
    turn_seconds: int = Field(default=15, ge=10, le=60)
    is_private: bool = False


class TableOut(BaseModel):
    id: str
    name: str
    mode: str
    status: str
    max_players: int
    boot_amount: int
    turn_seconds: int
    online_players: int = 0
    is_private: bool = False
    join_code: Optional[str] = None

    model_config = {"from_attributes": True}


# ---- WebSocket message payload (client -> server) ----------------------------------------
class WSAction(BaseModel):
    action: str  # see | bet | pack | side_show | side_show_respond | show | sync
    raise_: Optional[bool] = Field(default=None, alias="raise")  # for action="bet"
    accept: Optional[bool] = None  # for action="side_show_respond"
