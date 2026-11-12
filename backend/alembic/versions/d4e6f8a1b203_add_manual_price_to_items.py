# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: gpt-5 | 2026-11-03
"""Add a fallback price for manually created items.

Revision ID: d4e6f8a1b203
Revises: c3d5e8f0a912
Create Date: 2026-11-03 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6f8a1b203"
down_revision: str | None = "c3d5e8f0a912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("manual_price", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("items", "manual_price")
