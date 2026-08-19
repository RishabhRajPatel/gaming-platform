"""Engine-level errors. These are pure game-rule violations, independent of HTTP."""


class GameError(Exception):
    """Base class for all game-rule violations."""


class NotYourTurn(GameError):
    pass


class InvalidAction(GameError):
    pass


class CardNotInHand(GameError):
    pass


class GameStateError(GameError):
    pass
