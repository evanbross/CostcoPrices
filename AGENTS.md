# AI Agent Instructions — CostcoPrices

## Standards Files — Read These First

At the start of every session, re-read this file and each standards file below before making any changes.

- `../Dev-Standards/COMMON_CODING_STANDARDS.md`
- `../Dev-Standards/PYTHON_STANDARDS.md`
- `../Dev-Standards/DATABASE_STANDARDS.md`
- `../Dev-Standards/REACT_STANDARDS.md`
- `../Dev-Standards/FASTAPI_STANDARDS.md`
- `../Dev-Standards/TESTING_STANDARDS.md`
- `../Dev-Standards/INFRASTRUCTURE_STANDARDS.md`
- `../Dev-Standards/CODEX_CODING_STANDARDS.md`
- `../Dev-Standards/CODEX_SESSION_RULES.md`
- `../Dev-Standards/CODEX_REVIEW_CHECKLIST.md`
- `../Dev-Standards/GEMINI_SESSION_STANDARDS.md`

---

## Project Overview

Costco price-tracking app. Users upload screenshots of their Costco receipt pages; Claude's
vision API parses the line items; the user reviews/confirms them; the app saves them to SQLite
and tracks price history over time.

FastAPI backend (`backend/app/`) + TypeScript/React/Vite frontend (`frontend/src/`).
SQLite via SQLAlchemy 2.x; migrations managed by Alembic.
OCR powered by the Anthropic Claude API (vision). Run via `python main.py` at the project root.

### Key Files

**Backend**
- `backend/app/main.py` — FastAPI app, lifespan (DB init), router registration, static file mount
- `backend/app/config.py` — Pydantic Settings (DB path, Anthropic key, CORS)
- `backend/app/database/database.py` — SQLAlchemy engine, SessionLocal, `get_db` dependency
- `backend/app/database/schemas.py` — ALL Pydantic request/response models
- `backend/app/models/models.py` — ORM models: Item, Receipt, PriceHistory
- `backend/app/routes/items.py` — Item CRUD + friendly name update
- `backend/app/routes/receipts.py` — Image upload, OCR (Claude), confirm/save
- `backend/app/routes/reports.py` — Import summary (new/changed/unchanged items)
- `backend/app/services/ocr_service.py` — Claude vision API call; returns ParsedLine list
- `backend/app/services/receipt_service.py` — Item upsert, price_history insert, ImportReport

**Frontend**
- `frontend/src/App.tsx` — React Router v6 route definitions
- `frontend/src/types/index.ts` — ALL shared TypeScript interfaces
- `frontend/src/api/client.ts` — Axios instance (baseURL=/api) + typed API functions
- `frontend/src/pages/` — Dashboard, Items, ItemDetail, Receipts, Reports
- `frontend/src/components/` — Layout, Navbar, ReceiptUploadZone, ReceiptReviewDialog, EditItemDialog, PriceHistoryTable

**Orchestrator**
- `main.py` — Checks if frontend/dist is stale, rebuilds via `npm run build`, then starts uvicorn.
  Pass `--dev` to run Vite dev server alongside uvicorn with hot-reload.

### Receipt Format (Costco)

Each line: `[optional letter] <item_code> <description> <price> <tax_char>`
- `tax_char` `3` = grocery, `Y` = prepared food
- Lines starting with `/` followed by an item_code are coupons/discounts

### Costco Brand Colors

```
#E31837  — Costco red (primary)
#003087  — Costco blue (nav/secondary)
#B8860B  — Kirkland gold (accents)
#F5F5F5  — light background
```
