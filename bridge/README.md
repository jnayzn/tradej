# MT5 → Trading Journal bridge

A small Python script that runs on the **Windows** machine where MetaTrader 5
is installed and pushes your closed deals to the Trading Journal API.

> **Why Windows?** The official `MetaTrader5` Python package only ships
> Windows wheels. On macOS / Linux, run this script inside a Windows VM, or
> use the **CSV/JSON import** in the dashboard instead.

## Install

```powershell
cd bridge
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configure MT5

Inside the MT5 terminal:

1. **Tools → Options → Expert Advisors** → enable *Allow algorithmic trading* and *Allow DLL imports*.
2. Make sure the terminal is **logged into the trading account** you want to journal.
3. Leave the terminal **running** while the bridge script executes.

## Live sync (recommended): `--watch` mode

Run the bridge as a long-running process that polls MT5 every few seconds
and posts every newly closed position to the journal:

```powershell
python mt5_bridge.py --api-url http://localhost:8000/api --watch --interval 30
```

What this does on every tick (default every 30s):

1. Queries MT5 for closed deals since the last persisted highwater mark
   (overlapping by 60s to catch trades that close right on the boundary).
2. Aggregates them into closed positions.
3. POSTs only the *new* records to `/api/trades/import/`.
4. Persists the new highwater mark to `--state-file` (default
   `%USERPROFILE%\.trading-journal-bridge.json`).

Result: a position closed in MT5 appears on the journal **within `--interval`
seconds**, with no manual export.

The daemon survives transient errors:

- **Network errors / 5xx** → exponential backoff (up to `--max-retries`, default 5).
- **4xx** (bad payload, auth) → not retried; logged.
- **MT5 returns nothing or raises** → the tick is logged and the loop
  continues; you don't have to restart the script.
- **`Ctrl+C` / `SIGTERM`** → finishes the current tick, persists state, exits cleanly.

### Run it as a Windows service (so it auto-starts at login)

The simplest robust option is [NSSM](https://nssm.cc/) (the Non-Sucking
Service Manager):

```powershell
# 1. Download nssm.exe and put it on PATH.
# 2. Install the service:
nssm install TradingJournalBridge ^
    "C:\path\to\bridge\.venv\Scripts\python.exe" ^
    mt5_bridge.py ^
    --api-url https://your-backend/api ^
    --watch --interval 30

# 3. Set the working directory and tell it to restart on failure.
nssm set TradingJournalBridge AppDirectory "C:\path\to\bridge"
nssm set TradingJournalBridge AppExit Default Restart
nssm set TradingJournalBridge AppStdout "C:\path\to\bridge\bridge.log"
nssm set TradingJournalBridge AppStderr "C:\path\to\bridge\bridge.log"

# 4. Start it:
nssm start TradingJournalBridge
```

### Alternative: a 1-minute cron via Task Scheduler

If you'd rather not run a long-lived process:

1. Open Task Scheduler → *Create Basic Task…*
2. Trigger: *Daily*, every 1 day, at e.g. `23:55`. (Or *At log on*, repeat every minute for 1 day.)
3. Action: *Start a program*.
   - Program/script: `C:\path\to\bridge\.venv\Scripts\python.exe`
   - Arguments: `mt5_bridge.py --api-url https://your-backend/api --days 2`
   - Start in: `C:\path\to\bridge`

The server deduplicates trades by their MT5 ticket, so it's safe to run the
bridge as often as you like.

## One-shot mode (backfill or scheduled task)

```powershell
python mt5_bridge.py --api-url http://localhost:8000/api --days 30
```

Optionally log into a specific account from the script (otherwise the active
terminal session is used):

```powershell
python mt5_bridge.py --login 1234567 --password "secret" --server "ICMarkets-Demo" --days 60
```

To preview the payload without uploading:

```powershell
python mt5_bridge.py --dry-run --days 7
```

## CLI reference

| Flag | Default | Purpose |
| --- | --- | --- |
| `--api-url` | `http://localhost:8000/api` (or `$TRADING_JOURNAL_API_URL`) | Backend API base URL. |
| `--days` | `30` | Lookback window in days (one-shot, and first watch tick). |
| `--watch` | off | Run continuously, polling every `--interval` seconds. |
| `--interval` | `30` | Watch-mode polling interval (seconds). |
| `--state-file` | `~/.trading-journal-bridge.json` | Where to persist the watch-mode highwater mark. |
| `--max-retries` | `5` | Max HTTP retry attempts on transient errors. |
| `--login` / `--password` / `--server` | (use active session) | Pre-authenticate to a specific MT5 account. |
| `--terminal-path` | (auto-detect) | Path to `terminal64.exe` if MT5 is not on PATH. |
| `--dry-run` | off | Print payload, do not POST. |

## How it works

The script calls `mt5.history_deals_get(start, end)` and aggregates the
returned deals by `position_id`, emitting one record per closed position. The
records are POSTed to `/api/trades/import/`. See the source for details.

## Tests

The pure-Python helpers (order-type derivation, state persistence, retry,
the watch loop) are covered by `test_mt5_bridge.py` and run cleanly without
the Windows-only `MetaTrader5` package:

```bash
cd bridge
python -m unittest test_mt5_bridge -v
```
