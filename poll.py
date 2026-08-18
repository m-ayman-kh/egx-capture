#!/usr/bin/env python3
"""
EGX price recorder — runs on GitHub Actions every 5 minutes during trading hours.

Fetches live quotes for the whole universe from the TradingView scanner (no key,
no browser) and folds them into egx-live.json, mirroring the capture logic the
dashboard's LIVE layer uses:
  - true open  = first reading >= 15 min into the session (the feed reports the
                 previous close as "open" before that, so we ignore it early)
  - h / l      = the feed's latest values (never accumulated across the day)
  - hObs/lObs  = independent max/min of prices we actually saw (5-min sampling)
  - t[]        = [minutesSinceMidnightCairo, price, cumulativeVolume] per poll

Only writes during an EGX session, so out-of-hours cron ticks make no commit.
Set env FORCE_PROBE=1 (the manual "Run workflow" button does this) to also drop
egx-probe.json with a small sample, so reachability can be confirmed any time.
"""
import json, os, sys, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

SCANNER = "https://scanner.tradingview.com/egypt/scan"
COLUMNS = ["name", "close", "change", "volume", "open", "high", "low", "update_mode"]
CAIRO = ZoneInfo("Africa/Cairo")
STORE = "egx-live.json"
KEEP_DAYS = 12            # matches the dashboard's KEEP_TICK_DAYS
BATCH = 60

def load_tickers():
    with open("tickers.txt") as f:
        return [ln.strip() for ln in f if ln.strip()]

def fetch(tickers):
    body = json.dumps({
        "symbols": {"tickers": ["EGX:" + t for t in tickers], "query": {"types": []}},
        "columns": COLUMNS,
    }).encode()
    req = urllib.request.Request(SCANNER, data=body, headers={
        "Content-Type": "text/plain",
        "User-Agent": "Mozilla/5.0 (compatible; egx-capture/1)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    out = {}
    for row in j.get("data", []):
        d = row["d"]
        out[d[0]] = {"close": d[1], "chg": d[2], "vol": d[3],
                     "open": d[4], "high": d[5], "low": d[6], "mode": d[7]}
    return out

def fetch_all(tickers):
    quotes = {}
    for i in range(0, len(tickers), BATCH):
        quotes.update(fetch(tickers[i:i + BATCH]))
    return quotes

def session_state(now):
    mins = now.hour * 60 + now.minute
    weekday = now.weekday()          # Mon=0 .. Sun=6
    trading_day = weekday in (6, 0, 1, 2, 3)   # Sun..Thu
    is_open = trading_day and 600 <= mins <= 885   # 10:00 - 14:45 Cairo
    return is_open, mins

def capture(store, quotes, day, mins):
    settled = (mins - 600) >= 15
    bars = store.setdefault("days", {}).setdefault(day, {})
    for sym, q in quotes.items():
        c = q["close"]
        if c is None:
            continue
        rec = bars.get(sym)
        if rec is None:
            rec = bars[sym] = {"o": c if settled else None, "oCaptured": bool(settled),
                               "h": q["high"], "l": q["low"], "c": c, "v": q["vol"],
                               "hObs": c, "lObs": c, "n": 0, "t": []}
        if not rec["oCaptured"] and settled:
            rec["o"] = c
            rec["oCaptured"] = True
        rec["h"] = q["high"]
        rec["l"] = q["low"]
        rec["hObs"] = max(rec["hObs"] if rec["hObs"] is not None else c, c)
        rec["lObs"] = min(rec["lObs"] if rec["lObs"] is not None else c, c)
        rec["c"] = c
        rec["v"] = q["vol"]
        rec["n"] += 1
        t = rec["t"]
        sample = [mins, c, q["vol"] or 0]
        if not t or t[-1][0] != mins:
            t.append(sample)
        else:
            t[-1] = sample

def prune(store):
    days = sorted(store.get("days", {}))
    for d in days[:-KEEP_DAYS]:
        del store["days"][d]

def main():
    tickers = load_tickers()
    now = datetime.now(CAIRO)
    is_open, mins = session_state(now)
    day = now.strftime("%Y-%m-%d")

    try:
        quotes = fetch_all(tickers)
        err = None
    except Exception as e:
        quotes, err = {}, repr(e)

    if os.environ.get("FORCE_PROBE") == "1":
        sample = {k: quotes[k] for k in list(quotes)[:5]}
        json.dump({"ran_utc": datetime.utcnow().isoformat() + "Z",
                   "cairo": now.isoformat(), "session_open": is_open,
                   "quotes_returned": len(quotes), "error": err, "sample": sample},
                  open("egx-probe.json", "w"), indent=2)

    if err:
        print("fetch error:", err)
        sys.exit(0 if os.environ.get("FORCE_PROBE") == "1" else 1)

    if not is_open:
        print(f"market closed ({now:%a %H:%M} Cairo) — {len(quotes)} quotes, no write")
        return

    try:
        store = json.load(open(STORE))
    except (FileNotFoundError, json.JSONDecodeError):
        store = {"schema": 1, "days": {}}

    capture(store, quotes, day, mins)
    prune(store)
    store["updated"] = datetime.utcnow().isoformat() + "Z"
    store["day"] = day
    json.dump(store, open(STORE, "w"), separators=(",", ":"))
    print(f"captured {len(quotes)} quotes into {day} at {mins-600} min into session")

if __name__ == "__main__":
    main()
