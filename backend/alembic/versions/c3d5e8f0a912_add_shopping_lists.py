"""add shopping lists

Revision ID: c3d5e8f0a912
Revises: a1c9d3e7f820
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d5e8f0a912'
down_revision: Union[str, None] = 'a1c9d3e7f820'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shopping_lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'shopping_list_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('shopping_lists.id'), nullable=False, index=True),
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('items.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(8, 3), nullable=False, server_default='1'),
        sa.Column('note', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('shopping_list_items')
    op.drop_table('shopping_lists')
