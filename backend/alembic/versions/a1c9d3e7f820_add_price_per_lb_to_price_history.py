"""add price_per_lb to price_history

Revision ID: a1c9d3e7f820
Revises: f8e06775b452
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c9d3e7f820'
down_revision: Union[str, None] = 'f8e06775b452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('price_history', sa.Column('price_per_lb', sa.Numeric(10, 4), nullable=True))


def downgrade() -> None:
    op.drop_column('price_history', 'price_per_lb')
