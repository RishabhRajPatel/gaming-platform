"""add andar_bahar_tables, table_id on andar_bahar_rounds

Revision ID: addd26a878d7
Revises: 325644762c4e
Create Date: 2026-08-20 15:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'addd26a878d7'
down_revision: Union[str, None] = '325644762c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Named distinctly from "tablemode"/"tablestatus" (Deals Rummy's GameTable,
    # initial-schema migration) and "teen_patti_table_mode"/"_status" (Teen Patti's
    # own table) — three modules independently define same-named `TableMode`/
    # `TableStatus` Python enum classes with different values; sharing a Postgres
    # enum type name across them is a CREATE TYPE collision (SQLite has no native
    # enum type, so this only bites on Postgres, which is why it's easy to miss).
    op.create_table('andar_bahar_tables',
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('mode', sa.Enum('VIRTUAL', 'REAL', name='andar_bahar_table_mode'), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'RUNNING', 'FINISHED', name='andar_bahar_table_status'), nullable=False),
    sa.Column('max_players', sa.Integer(), nullable=False),
    sa.Column('betting_seconds', sa.Integer(), nullable=False),
    sa.Column('is_private', sa.Boolean(), nullable=False),
    sa.Column('join_code', sa.String(length=8), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_andar_bahar_tables_join_code'), 'andar_bahar_tables', ['join_code'], unique=True)

    op.add_column('andar_bahar_rounds', sa.Column('table_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_andar_bahar_rounds_table_id'), 'andar_bahar_rounds', ['table_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_andar_bahar_rounds_table_id'), table_name='andar_bahar_rounds')
    op.drop_column('andar_bahar_rounds', 'table_id')

    op.drop_index(op.f('ix_andar_bahar_tables_join_code'), table_name='andar_bahar_tables')
    op.drop_table('andar_bahar_tables')
    sa.Enum(name='andar_bahar_table_mode').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='andar_bahar_table_status').drop(op.get_bind(), checkfirst=True)
