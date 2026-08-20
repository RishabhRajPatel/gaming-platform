"""add teen_patti_tables

Revision ID: 325644762c4e
Revises: a766207350f4
Create Date: 2026-08-20 12:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '325644762c4e'
down_revision: Union[str, None] = 'a766207350f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Named distinctly from the "tablemode"/"tablestatus" Postgres enum types the
    # initial-schema migration already created for Deals Rummy's GameTable (same
    # Python class names, same default type name — this table's own mode/status
    # values ("virtual"/"real") differ from Rummy's ("real_money"/"free") anyway, so
    # sharing the type would have been wrong even without the CREATE TYPE collision).
    op.create_table('teen_patti_tables',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('mode', sa.Enum('VIRTUAL', 'REAL', name='teen_patti_table_mode'), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'RUNNING', 'FINISHED', name='teen_patti_table_status'), nullable=False),
    sa.Column('max_players', sa.Integer(), nullable=False),
    sa.Column('boot_amount', sa.BigInteger(), nullable=False),
    sa.Column('turn_seconds', sa.Integer(), nullable=False),
    sa.Column('is_private', sa.Boolean(), nullable=False),
    sa.Column('join_code', sa.String(length=8), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teen_patti_tables_join_code'), 'teen_patti_tables', ['join_code'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_teen_patti_tables_join_code'), table_name='teen_patti_tables')
    op.drop_table('teen_patti_tables')
    sa.Enum(name='teen_patti_table_mode').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='teen_patti_table_status').drop(op.get_bind(), checkfirst=True)
