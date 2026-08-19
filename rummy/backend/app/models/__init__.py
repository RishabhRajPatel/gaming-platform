"""Import every model so Alembic autogenerate can see the full metadata."""
from app.models.audit import AuditLog
from app.models.game import GameRound, GameTable, TableMode, TableStatus
from app.models.otp import OtpCode, OtpPurpose
from app.models.payment import (
    Deposit,
    PaymentStatus,
    Withdrawal,
    WithdrawalStatus,
)
from app.models.user import KYCStatus, User, UserRole
from app.models.wallet import (
    TxnType,
    Wallet,
    WalletKind,
    WalletTransaction,
)

__all__ = [
    "AuditLog",
    "GameRound", "GameTable", "TableMode", "TableStatus",
    "OtpCode", "OtpPurpose",
    "Deposit", "PaymentStatus", "Withdrawal", "WithdrawalStatus",
    "User", "UserRole", "KYCStatus",
    "Wallet", "WalletTransaction", "TxnType", "WalletKind",
]
