# Testing the Trading Journal app

The app is a Django backend + React/Vite frontend monorepo with a separate
MT5 bridge. This skill documents how to bring the stack up locally, run the
unit tests across all three layers, and drive the primary import flow end-to-end
from the UI.

## Stack overview

| Layer | Path | Port | Tech |
|---|---|---|---|
| Backend | `backend/` | 8000 | Django 5 + DRF, SQLite (dev), Postgres (prod) |
| Frontend | `frontend/` | 5173 | Vite + React 18 + TS + Tailwind |
| Bridge | `bridge/` | — | Pure Python, MetaTrader5 (Windows-only at runtime) |

The environment.yaml `maintenance` block already installs everything the
first-time-around (backend `.venv` + requirements + migrations, frontend
`npm ci`, plus `requests` for the bridge tests). Use those commands as your
source of truth.

## Run the unit tests

```bash
# Backend (Django)
cd backend && . .venv/bin/activate
DJANGO_SECRET_KEY=test python manage.py test --verbosity=1
ruff check . && ruff format --check .

# Bridge (pure-Python helpers — MetaTrader5 not needed)
cd bridge && ../backend/.venv/bin/python -m unittest test_mt5_bridge -v

# Frontend
cd frontend && npm run lint && npm run typecheck && npm run build
```

At the time of writing, backend has 16 tests, bridge has 2, and the frontend
builds clean. CI runs all three jobs in `.github/workflows/ci.yml`.

## Bring up the dev servers locally

```bash
# Terminal 1 — backend on :8000
cd backend && . .venv/bin/activate && \
  DJANGO_SECRET_KEY=dev DJANGO_DEBUG=true CORS_ALLOWED_ORIGINS=http://localhost:5173 \
  python manage.py runserver 0.0.0.0:8000

# Terminal 2 — frontend on :5173
cd frontend && VITE_API_BASE_URL=http://localhost:8000/api npm run dev -- --host 0.0.0.0
```

For a clean recording / empty-state test, wipe the SQLite DB before starting:
```bash
rm -f backend/db.sqlite3
cd backend && DJANGO_SECRET_KEY=dev ./.venv/bin/python manage.py migrate --noinput
```

## Test fixtures

- `samples/mt5_history.csv` — 20 trades across 4 symbols (EURUSD, XAUUSD,
  GBPUSD, USDJPY) covering May 2024. Includes a deliberate revenge-trade
  pattern (ticket 1009 → 1010) that the analytics engine should flag.
- `samples/api_export.json` — 1 AUDUSD trade shaped like the API's own JSON
  output (uses `order_type` field name). Useful for verifying the importer's
  `HEADER_ALIASES` identity mapping that PR #3 added.

## Expected fixture numbers (after importing `mt5_history.csv`)

- 20 trades, 70.0% winrate, $208.30 total PnL, 3.15 profit factor
- Biggest win $56.50, biggest loss −$44.10
- Avg win $21.81, avg loss −$16.18
- Trader score 72/100 ("Strong")
- Risk/Reward 1.35
- Findings: "Revenge trading pattern — 1 time(s)" + "Strategy is net profitable"
- May 2024 calendar: 12 green / 5 red days, day 5/9 = −$53.80 (red revenge),
  5/10 = +$56.50 (green recovery)
- By-symbol: XAUUSD 5/80%/$100, GBPUSD 4/100%/$69.60, USDJPY 3/66.7%/$64.70,
  EURUSD 8/50%/−$26.00

Re-importing the same CSV should report `Created 0, Updated 20, Skipped 0`.

## End-to-end UI flow

1. Open `http://localhost:5173/` — Dashboard route.
2. Sidebar has Dashboard / Trades / Calendar / Analytics + an **Import trades** button at the bottom.
3. Click **Import trades** → modal opens with a file input that accepts `.csv` and `.json`.
4. Choose the file and click **Upload** — the import runs against `POST /api/trades/import/`.
5. The modal shows a `Created / Updated / Skipped` summary and dispatches a
   `trades:imported` custom event. All pages listening via the `useReload`
   hook (`frontend/src/lib/useReload.ts`) refetch immediately — no page reload.

### Gotcha: Import button drops below the fold once data is loaded

The sidebar uses `mt-auto` to pin **Import trades** to the bottom of the
aside, but the aside is part of a `min-h-screen` flex container, so it grows
with the content. After importing trades the Dashboard becomes taller than
the viewport and the Import button moves below the fold. Press **End** or
scroll to the bottom of the page to find it again.

### Calendar navigation

The Calendar page lands on the current month. To reach the May 2024 fixture
data, click **Prev** (top-right of the calendar grid). It typically takes 24+
clicks from a current date — easier to verify the underlying API directly:

```bash
curl -s 'http://localhost:8000/api/stats/calendar/?year=2024&month=5'
```

## Bridge testing on Linux

The MT5 Python package is Windows-only, but `bridge/test_mt5_bridge.py`
exercises pure helpers using `SimpleNamespace` deals so it runs anywhere. The
bridge module imports `requests` at module level — make sure that's
installed in the venv (the env's `maintenance` step does this). The test
covers both branches of `_position_order_type`:

- Open deal in scope → use opening deal type directly.
- Open deal outside lookback → invert closing deal type (in MT5 a BUY
  position closes with a SELL deal and vice versa).

## API quick reference

- `GET /api/trades/?limit=10&offset=0` — paginated trade list (search via `?search=`)
- `POST /api/trades/import/` — multipart `file` *or* JSON body. Accepts `.csv`/`.json` or `{"trades": [...]}`. Deduplicates by `ticket`.
- `GET /api/stats/summary/` — total/winrate/profit-factor/etc.
- `GET /api/stats/equity/` — cumulative PnL points
- `GET /api/stats/calendar/?year=YYYY&month=M` — per-day aggregation for one month
- `GET /api/stats/by-symbol/` — per-symbol breakdown
- `GET /api/stats/insights/` — trader score, findings, metrics

## CI checks status

The repo has a 3-job workflow at `.github/workflows/ci.yml` (Backend / Bridge
/ Frontend). If all jobs report "The job was not started because your
account is locked due to a billing issue", the failures are not in the code
— resolve at https://github.com/settings/billing.
