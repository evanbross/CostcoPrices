# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-28
"""Shared fixtures: a fresh in-memory SQLite schema per test (a real DB, not a mock)."""
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.models  # noqa: F401 — registers every table on Base.metadata
from app.database.database import Base


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    # StaticPool: an in-memory SQLite DB lives only as long as its connection, so
    # every session in the test must share that one connection.
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, autoflush=False, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()
