"""merge heads, add teen_patti_hand_history

Merges the two dangling migration heads left after `add andar_bahar_rounds` was
branched off `initial schema` in parallel with the `phone auth / private tables /
pool rummy` chain, and adds the Teen Patti hand-history table.

Revision ID: a766207350f4
Revises: 2487148369c6, 8f537f6c6eee
Create Date: 2026-08-20 12:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a766207350f4'
down_revision: Union[str, Sequence[str], None] = ('2487148369c6', '8f537f6c6eee')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('teen_patti_hand_history',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('table_id', sa.String(length=36), nullable=True),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('boot', sa.BigInteger(), nullable=False),
    sa.Column('pot', sa.BigInteger(), nullable=False),
    sa.Column('winner_seat', sa.Integer(), nullable=False),
    sa.Column('won', sa.Boolean(), nullable=False),
    sa.Column('payout', sa.BigInteger(), nullable=False),
    sa.Column('hand_json', sa.String(), nullable=False),
    sa.Column('client_seed', sa.String(length=120), nullable=False),
    sa.Column('nonce', sa.BigInteger(), nullable=False),
    sa.Column('server_seed', sa.String(length=64), nullable=False),
    sa.Column('server_seed_hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teen_patti_hand_history_user_id'), 'teen_patti_hand_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_teen_patti_hand_history_table_id'), 'teen_patti_hand_history', ['table_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_teen_patti_hand_history_table_id'), table_name='teen_patti_hand_history')
    op.drop_index(op.f('ix_teen_patti_hand_history_user_id'), table_name='teen_patti_hand_history')
    op.drop_table('teen_patti_hand_history')
