"""Pure-Python Deals Rummy rules engine.

No framework, DB or network imports belong in this package. Everything here is
deterministic given a seed, which makes it fully unit-testable and reusable by bots,
replay tooling and the WebSocket server alike.
"""
from .cards import Card, Shoe, Suit, build_shoe, rank_points
from .deals_rummy import (
    DealsRummyGame,
    GameConfig,
    Phase,
    Player,
    PlayerStatus,
)
from .errors import GameError, InvalidAction, NotYourTurn
from .melds import MeldType, classify_meld, is_pure_sequence, is_sequence
from .scoring import best_hand_score, validate_declaration

__all__ = [
    "Card", "Shoe", "Suit", "build_shoe", "rank_points",
    "DealsRummyGame", "GameConfig", "Phase", "Player", "PlayerStatus",
    "GameError", "InvalidAction", "NotYourTurn",
    "MeldType", "classify_meld", "is_pure_sequence", "is_sequence",
    "best_hand_score", "validate_declaration",
]
