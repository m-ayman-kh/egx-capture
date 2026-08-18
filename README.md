# EGX price recorder (GitHub Actions)

This records EGX prices in the cloud every 5 minutes during trading hours, so the
data is captured even when your Mac is off. Your dashboard then reads the recorded
file. No holdings or personal data live here — market prices only.

## What's in this folder
- `poll.py` — fetches quotes from the TradingView scanner and updates `egx-live.json`
- `tickers.txt` — the 244 EGX symbols to record
- `.github/workflows/capture.yml` — the schedule that runs `poll.py` every 5 min, Sun–Thu
- `egx-live.json` — created on the first live run (the recorded data)

## One-time setup (about 5 minutes)
1. Create a **free GitHub account** if you don't have one: https://github.com/signup
2. Create a **new public repository** (name it e.g. `egx-capture`). Public is required so
   the dashboard can read the file without a password. Nothing sensitive is stored here.
3. Upload every file in this folder to the repo, keeping the `.github/workflows/` folder
   structure. (On github.com: "Add file" → "Upload files", then drag them in.)
4. Open the repo's **Actions** tab and click **"I understand my workflows, enable them"**.

## Prove it works before relying on it
- In the **Actions** tab, open **"EGX capture"** → **"Run workflow"** (the manual button).
- After it finishes, a file **`egx-probe.json`** appears in the repo. Open it:
  - `"quotes_returned"` should be around 240 (not 0) and `"error"` should be `null`.
  - If it shows an error or 0 quotes, the scanner refused the server call — tell me and
    we switch the fetch approach. This is the one thing that can't be tested from your Mac.

## After it's confirmed
- The schedule runs itself every 5 minutes, 07:00–12:59 UTC, Sunday–Thursday. That window
  covers EGX 10:00–14:45 Cairo year-round; `poll.py` ignores ticks outside the real session.
- `egx-live.json` fills up during each trading day. It keeps the last 12 days of intraday
  detail and the daily open/high/low/close/volume.

## Notes
- GitHub's scheduler is best-effort and can be a few minutes late or skip a tick under load.
  Fine for the true open and the daily bar; intraday spacing may be slightly uneven.
- The recorded "open" is the real opening price (first reading 15+ min after 10:00) — better
  than the feeds, which report the previous close as the open.
- Next step (separate): point the dashboard at `egx-live.json` so it shows this data on open
  and you never click "Go live" again.
