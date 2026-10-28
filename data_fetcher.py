"""All yfinance access lives here. Every function fails soft (returns empty/None)."""
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

import config
import db_manager


def _extract_close(raw, tickers):
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]                     # auto_adjust=True -> adjusted prices
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna(axis=1, how="all").sort_index()


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def _download(tickers: tuple, years: int) -> pd.DataFrame:
    raw = yf.download(list(tickers), period=f"{years}y", interval="1d", auto_adjust=True,
                      progress=False, threads=True)
    df = _extract_close(raw, tickers)
    if df.empty:                       # raising (not returning empty) keeps a failure out of the 1-hour cache
        raise RuntimeError("Yahoo Finance returned no price data (it may be rate-limiting this server).")
    return df


SNAP_DIR = Path(__file__).parent / "data_snapshot"      # created by make_snapshot.py and committed to GitHub


@st.cache_data(ttl=3600, show_spinner=False)
def _snapshot_prices() -> pd.DataFrame:
    """Saved price history used ONLY when Yahoo is unavailable. Empty frame if no snapshot exists."""
    p = SNAP_DIR / "prices.csv"
    try:
        return pd.read_csv(p, index_col=0, parse_dates=True).sort_index() if p.exists() else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _snapshot_info() -> dict:
    p = SNAP_DIR / "company_info.csv"
    try:
        df = pd.read_csv(p).fillna("") if p.exists() else pd.DataFrame()
        return {r["ticker"]: {"name": r["name"] or r["ticker"], "sector": r["sector"] or "Unknown", "industry": r["industry"]}
                for _, r in df.iterrows()}
    except Exception:
        return {}


def _mark_snapshot(df, err=""):
    """Remember (per user session) that saved data was used, so the page can show a banner."""
    try:
        ss = st.session_state
        ss["_data_snapshot"] = max(str(ss.get("_data_snapshot") or ""), str(df.index.max().date()))
        if err:
            ss["_data_error"] = err[:250]
    except Exception:
        pass


def _note_error(err):
    try:
        st.session_state["_data_error"] = err[:250]
    except Exception:
        pass


def get_prices(tickers, years: int) -> pd.DataFrame:
    """Adjusted close for many tickers. Order of attempts: one batch call; each missing ticker on its own;
    then the saved snapshot for anything still missing. Empty frame if everything fails."""
    tickers = tuple(sorted({t.upper().strip() for t in tickers}))
    if not tickers:
        return pd.DataFrame()
    err = ""
    try:
        df = _download(tickers, years)
    except Exception as e:
        df, err = pd.DataFrame(), f"{type(e).__name__}: {e}"
    for t in [t for t in tickers if t not in df.columns]:        # individual retry
        try:
            one = _download((t,), years)
        except Exception as e:
            err = err or f"{type(e).__name__}: {e}"
            continue
        if t in one.columns:
            df = one[[t]] if df.empty else df.join(one[[t]], how="outer")
    missing = [t for t in tickers if t not in df.columns]
    if missing:
        snap = _snapshot_prices()
        have = [t for t in missing if t in snap.columns]
        if have:
            part = snap.loc[snap.index >= snap.index.max() - pd.DateOffset(years=years), have].dropna(how="all")
            if not part.empty:
                df = part if df.empty else df.join(part, how="outer")
                _mark_snapshot(part, err)
        elif err:
            _note_error(err)
    return df.sort_index()


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def _download_range(tickers: tuple, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(list(tickers), start=start, end=end, interval="1d", auto_adjust=True,
                      progress=False, threads=True)
    df = _extract_close(raw, tickers)
    if df.empty:
        raise RuntimeError("Yahoo Finance returned no price data (it may be rate-limiting this server).")
    return df


def get_prices_range(tickers, start: str, end: str) -> pd.DataFrame:
    """Prices between two dates (used for stress tests that reach back before the lookback)."""
    tickers = tuple(sorted({t.upper().strip() for t in tickers}))
    try:
        return _download_range(tickers, start, end)
    except Exception as e:
        snap = _snapshot_prices()
        have = [t for t in tickers if t in snap.columns]
        part = snap.loc[start:end, have].dropna(how="all") if have else pd.DataFrame()
        if not part.empty:
            _mark_snapshot(part, f"{type(e).__name__}: {e}")
        return part


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def _volumes(tickers: tuple) -> dict:
    raw = yf.download(list(tickers), period="3mo", interval="1d", auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        return {}
    vol = raw["Volume"]
    if isinstance(vol, pd.Series):
        vol = vol.to_frame(tickers[0])
    return vol.tail(20).mean().dropna().to_dict()


def get_avg_volume(tickers) -> dict:
    """20-day average daily volume (shares). {} on failure."""
    try:
        return _volumes(tuple(sorted({t.upper().strip() for t in tickers})))
    except Exception:
        return {}


def resolve_prices(prices: pd.DataFrame, tickers):
    """Save today's prices as 'last known' and find holdings that have no fresh price.
    Returns (fresh {ticker: price}, stale {ticker: (last_price, as_of)})."""
    latest = prices.ffill().iloc[-1].dropna() if not prices.empty else pd.Series(dtype=float)
    fresh = {t: float(latest[t]) for t in tickers if t in latest.index}
    try:
        db_manager.save_last_prices(fresh)
        stored = db_manager.get_last_prices()
    except Exception:
        stored = {}
    return fresh, {t: stored[t] for t in tickers if t not in fresh and t in stored}


def _fetch_info(ticker: str):
    """One live Yahoo info call. Returns a dict, or None if Yahoo gave nothing usable."""
    try:
        i = yf.Ticker(ticker).info
        name = i.get("shortName") or i.get("longName")
        if not name:
            return None
        return {"name": name, "sector": i.get("sector") or "Unknown", "industry": i.get("industry") or ""}
    except Exception:
        return None


def get_company_info(tickers) -> dict:
    """Company/sector info from the stored table; Yahoo is called only for tickers that are
    missing or older than config.COMPANY_INFO_MAX_AGE_DAYS, and results are saved back."""
    try:
        stored = db_manager.get_company_rows()
    except Exception:
        stored = {}
    out, fresh = {}, []
    for t in tickers:
        rec = stored.get(t)
        try:
            age = (datetime.now() - datetime.fromisoformat(str(rec["updated_at"]))).days if rec else None
        except Exception:
            age = None
        if rec and age is not None and age < config.COMPANY_INFO_MAX_AGE_DAYS:
            out[t] = rec
            continue
        snap_rec = _snapshot_info().get(t)
        if snap_rec:                                         # saved info: no live Yahoo call needed
            out[t] = snap_rec
            continue
        got = _fetch_info(t)
        if got:
            fresh.append({"ticker": t, **got}); out[t] = got
        else:
            out[t] = rec or {"name": t, "sector": "Unknown", "industry": ""}   # old record beats nothing
    try:
        db_manager.save_company_info(fresh)
    except Exception:
        pass
    return out


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def _validate_live(ticker: str) -> float:
    h = yf.Ticker(ticker).history(period="5d", auto_adjust=True)["Close"].dropna()
    if h.empty:
        raise ValueError("no data")                      # raising keeps failures out of the cache
    return float(h.iloc[-1])


def validate_ticker(ticker: str):
    """Return (is_valid, latest_price, name). Used to reject unknown tickers.
    If Yahoo is unavailable, tickers that are in the saved snapshot are still accepted."""
    try:
        px = _validate_live(ticker)
        return True, px, get_company_info([ticker])[ticker]["name"]
    except Exception:
        snap = _snapshot_prices()
        if ticker in snap.columns and snap[ticker].notna().any():
            _mark_snapshot(snap[[ticker]].dropna())
            return True, float(snap[ticker].dropna().iloc[-1]), _snapshot_info().get(ticker, {}).get("name", ticker)
        return False, None, None


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def get_risk_free_rate():
    """3-month T-bill (^IRX, quoted in percent). Returns (rate_as_fraction, source)."""
    try:
        h = yf.Ticker("^IRX").history(period="5d")["Close"].dropna()
        if not h.empty and 0 <= h.iloc[-1] < 25:
            return float(h.iloc[-1]) / 100, "3-month T-bill (^IRX)"
    except Exception:
        pass
    return config.FALLBACK_RF, "fallback default (^IRX unavailable)"
