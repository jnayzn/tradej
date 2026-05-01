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

## Run

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

## Schedule it

To keep your journal up to date in the background, schedule it with **Windows
Task Scheduler**:

1. Open Task Scheduler → *Create Basic Task…*
2. Trigger: *Daily*, every 1 day, at e.g. `23:55`.
3. Action: *Start a program*.
   - Program/script: `C:\path\to\bridge\.venv\Scripts\python.exe`
   - Arguments: `mt5_bridge.py --api-url https://your-backend/api --days 2`
   - Start in: `C:\path\to\bridge`

The server deduplicates trades by their MT5 ticket, so it's safe to run the
bridge as often as you like.

## How it works

The script calls `mt5.history_deals_get(start, end)` and aggregates the
returned deals by `position_id`, emitting one record per closed position. The
records are POSTed to `/api/trades/import/`. See the source for details.
