# Trading Journal

A SaaS-style trading journal for retail traders. Connect your MetaTrader 5 (MT5) account (or import a CSV/JSON export), automatically log every trade, and visualize your performance in a TradingView-inspired dark-themed dashboard.

> **Status:** v2 — multi-user auth, near-real-time MT5 sync (`--watch` mode), CSV/JSON import, dashboard, calendar, analytics, smart insights. Self-hostable for free with Railway + Vercel.

## Features

- **Trade ingestion**
  - CSV / JSON import (MT5 history export format supported out of the box)
  - Python desktop bridge script (`bridge/mt5_bridge.py`) that pulls trade history from a running MT5 terminal and pushes it to the API
  - REST API for programmatic ingestion (single trade or bulk)
- **Dashboard**
  - Total PnL, winrate, win/loss counts, biggest win / biggest loss, average win / average loss, profit factor, expectancy
  - Equity curve (cumulative PnL over time)
  - Recent trades table
- **Trades page** — paginated, filterable table with all trade fields
- **Calendar** — monthly heatmap, green/red days based on net PnL, daily trade counts
- **Analytics**
  - Per-symbol breakdown
  - PnL distribution
  - Smart insights: overtrading detection, revenge trading detection, win/loss ratio warnings, automatic trader score (0–100)
- **Dark theme** styled after TradingView / TraderVue, responsive layout

## Tech stack

| Layer | Tech |
| --- | --- |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, react-chartjs-2, React Router |
| Backend | Django 5, Django REST Framework, django-cors-headers, dj-database-url |
| Database | SQLite (dev) → PostgreSQL (prod) |
| Bridge | Python 3.10+, `MetaTrader5` package, `requests` |
| Deployment | Railway (backend + Postgres) + Vercel (frontend) |
| CI | GitHub Actions (lint + tests for backend & frontend) |

## Repo layout

```
trading-journal/
├── backend/        # Django + DRF API
├── frontend/       # React + Vite + Tailwind dashboard
├── bridge/         # MT5 → API bridge script (run on Windows)
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## Quick start (local dev)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

The API is now running at <http://localhost:8000/api/>.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard is now running at <http://localhost:5173>. It is preconfigured to talk to `http://localhost:8000/api/` (override with `VITE_API_BASE_URL`).

### Docker (one-shot)

```bash
docker compose up --build
```

This brings up the backend (with SQLite) on `:8000` and the frontend on `:5173`.

## Sign up & sign in

The API is multi-user. The first time you open the dashboard:

1. Click **Create one** on the login page.
2. Pick a username (3+ chars) and password (8+ chars). Email is optional.
3. You're in. Open the **Settings** page and copy your **API token** — the
   bridge needs it to push trades into your account.

Your trades are private to your account: two users on the same instance never
see each other's data, even if they have the same MT5 ticket numbers.

## Importing trades

### Option A — CSV/JSON upload from the UI

1. Open the dashboard, click **Import** in the sidebar.
2. Pick a `.csv` or `.json` file (MT5 history export format supported).
3. Trades are deduplicated per-user by `ticket` if provided.

### Option B — MT5 desktop bridge (live sync)

The bridge runs on your **Windows** machine where MT5 is installed (the `MetaTrader5` Python package is Windows-only).

```powershell
cd bridge
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python mt5_bridge.py --api-url http://localhost:8000/api `
                     --api-token <YOUR_TOKEN> `
                     --watch --interval 15
```

Get your `<YOUR_TOKEN>` from the **Settings** page of the dashboard. With
`--watch`, every position you close in MT5 lands on the dashboard within
`--interval` seconds, no manual export.

See [`bridge/README.md`](bridge/README.md) for the full set of options
(account login, server, lookback window, scheduling, running as a Windows
service).

### Option C — Direct API

```bash
curl -X POST http://localhost:8000/api/trades/import/ \
     -H "Authorization: Token <YOUR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d @my-trades.json
```

## Deployment

### Backend → Railway

1. Push the repo to GitHub.
2. Create a new Railway project from the repo, pointing to `backend/`.
3. Add a Postgres plugin; Railway exposes `DATABASE_URL` automatically.
4. Set environment variables:
   - `DJANGO_SECRET_KEY` — long random string
   - `DJANGO_DEBUG` — `false`
   - `DJANGO_ALLOWED_HOSTS` — your Railway domain (e.g. `trading-journal.up.railway.app`)
   - `CORS_ALLOWED_ORIGINS` — your Vercel frontend origin (e.g. `https://trading-journal.vercel.app`)
5. Railway auto-detects the Dockerfile in `backend/` and runs migrations + Gunicorn on boot.

### Frontend → Vercel

1. Import the repo in Vercel, set the **Root Directory** to `frontend/`.
2. Build command: `npm run build`. Output directory: `dist`.
3. Add env var `VITE_API_BASE_URL` pointing to your Railway backend (e.g. `https://trading-journal.up.railway.app/api`).

## Roadmap

- Bridge `.exe` built via PyInstaller in CI (so non-Python users can just
  download and run)
- Tagging / strategies / playbooks
- MAE / MFE charting
- Mobile-first refinements & PWA
- Optional Stripe billing if you want to run a paid hosted instance

## License

MIT
