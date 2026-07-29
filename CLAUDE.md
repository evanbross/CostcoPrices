@../Dev-Standards/COMMON_CODING_STANDARDS.md
@../Dev-Standards/PYTHON_STANDARDS.md
@../Dev-Standards/DATABASE_STANDARDS.md
@../Dev-Standards/JAVASCRIPT_TYPESCRIPT_STANDARDS.md
@../Dev-Standards/REACT_STANDARDS.md
@../Dev-Standards/FASTAPI_STANDARDS.md
@../Dev-Standards/TESTING_STANDARDS.md
@../Dev-Standards/INFRASTRUCTURE_STANDARDS.md
@../Dev-Standards/WINDOWS_STANDARDS.md

## SQLAlchemy / Python Datetime

Never use `datetime.utcnow` as a column default — deprecated in Python 3.12+. Always use `lambda: datetime.now(timezone.utc)`:

```python
# Wrong
created_at = Column(DateTime, default=datetime.utcnow)

# Right
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
```

## Pydantic Settings

Use `SettingsConfigDict` — the inner `class Config` pattern is deprecated in Pydantic v2:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
```

## Project Layout

- `backend/app/` — FastAPI application (Python/UV)
- `frontend/src/` — React 18 + TypeScript + Vite + Tailwind CSS
- `main.py` (root) — orchestrator: rebuilds frontend if stale, starts uvicorn
- `backend/app/database/schemas.py` — ALL Pydantic request/response models (never redeclare locally)
- `frontend/src/types/index.ts` — ALL shared TypeScript types (never redeclare locally)
