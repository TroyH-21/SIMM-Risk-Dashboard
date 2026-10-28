"""
Save a snapshot of market data so the Streamlit Cloud app still works when Yahoo Finance blocks it.

Run this on YOUR computer (home/campus internet is rarely rate-limited), then upload the new `data_snapshot` folder to GitHub:

    pip install -U yfinance
    python make_snapshot.py                 # all holdings + benchmarks
    python make_snapshot.py --extra NVDA,AMD    # also include tickers you plan to pitch

It writes data_snapshot/prices.csv (daily adjusted prices since Dec 2019, enough for the 5Y view and the stress tests) and
data_snapshot/company_info.csv (names, sectors, industries). The app only uses them when live Yahoo data fails, and it says so
with a banner. Re-run it whenever you want fresher saved data.
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

import config

OUT = Path(__file__).parent / "data_snapshot"


def held_tickers():
    import db_manager
    try:
        if hasattr(db_manager, "seed_if_empty"):
            db_manager.seed_if_empty()
    except Exception as e:
        print("seed step skipped:", e)
    found = set()
    for p in config.PORTFOLIOS:
        try:
            found |= set(db_manager.get_holdings(p)["ticker"])
        except Exception as e:
            print(f"Could not read holdings for {p}: {e}")
    return found | {config.BENCHMARK, *config.PORTFOLIO_BENCHMARKS.values()}


def close_frame(raw, tickers):
    if raw is None or raw.empty:
        return pd.DataFrame()
    c = raw["Close"]
    if isinstance(c, pd.Series):
        c = c.to_frame(tickers[0])
    c.index = pd.to_datetime(c.index).tz_localize(None)
    return c.dropna(axis=1, how="all")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extra", default="", help="comma-separated extra tickers, e.g. NVDA,AMD")
    ap.add_argument("--start", default="2019-12-01")
    a = ap.parse_args()
    tickers = sorted(held_tickers() | {t.strip().upper() for t in a.extra.split(",") if t.strip()})
    if not tickers:
        raise SystemExit("No tickers found.")
    print(f"Downloading {len(tickers)} tickers since {a.start} ...")
    df = close_frame(yf.download(tickers, start=a.start, interval="1d", auto_adjust=True, progress=False, threads=True), tickers)
    for t in [t for t in tickers if t not in df.columns]:
        time.sleep(1)
        one = close_frame(yf.download([t], start=a.start, interval="1d", auto_adjust=True, progress=False), [t])
        if t in one.columns:
            df = one[[t]] if df.empty else df.join(one[[t]], how="outer")
    if df.empty:
        raise SystemExit("Yahoo returned no data. Try again later, on a different network, or after `pip install -U yfinance`.")
    missing = [t for t in tickers if t not in df.columns]
    rows = []
    for t in tickers:
        try:
            i = yf.Ticker(t).info
            rows.append({"ticker": t, "name": i.get("shortName") or i.get("longName") or t,
                         "sector": i.get("sector") or "Unknown", "industry": i.get("industry") or ""})
        except Exception:
            rows.append({"ticker": t, "name": t, "sector": "Unknown", "industry": ""})
        time.sleep(0.3)
    OUT.mkdir(exist_ok=True)
    df.sort_index().round(6).to_csv(OUT / "prices.csv")
    pd.DataFrame(rows).to_csv(OUT / "company_info.csv", index=False)
    print(f"Saved {df.shape[1]} tickers x {df.shape[0]} days (through {df.index.max().date()}) to {OUT}.")
    if missing:
        print("No data for:", ", ".join(missing))
    print("Now upload the whole data_snapshot folder to GitHub (same level as app.py) and reboot the app.")


if __name__ == "__main__":
    main()
