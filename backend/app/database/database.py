# ai: claude-sonnet-4-6 | 2026-06-18
from collections.abc import AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ai: claude-opus-5-5 | 2026-09-28
# DATABASE_URL stays in its plain sync form because Alembic migrates with a sync
# engine; the app derives its async driver from that one value so they can't drift.
_ASYNC_DRIVERS = {"sqlite": "sqlite+aiosqlite"}


def async_database_url(url: str) -> URL:
    parsed = make_url(url)
    async_driver = _ASYNC_DRIVERS.get(parsed.drivername)
    if async_driver is None:
        raise ValueError(
            f"No async driver configured for database driver '{parsed.drivername}'. "
            f"Supported: {', '.join(_ASYNC_DRIVERS)}."
        )
    return parsed.set(drivername=async_driver)


engine = create_async_engine(async_database_url(settings.database_url))
# expire_on_commit=False: an async session can't lazily reload expired attributes,
# so objects must stay readable after commit when routes build their responses.
SessionLocal = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ai: claude-opus-5-5 | 2026-09-28
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as db:
        yield db
