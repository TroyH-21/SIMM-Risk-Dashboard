"""All yfinance access lives here. Every function fails soft (returns empty/None)."""
from datetime import datetime

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
    return _extract_close(raw, tickers)


def get_prices(tickers, years: int) -> pd.DataFrame:
    """Adjusted close for many tickers in one batch call. If the batch fails or misses tickers,
    each missing ticker is retried on its own. Empty frame if everything fails."""
    tickers = tuple(sorted({t.upper().strip() for t in tickers}))
    if not tickers:
        return pd.DataFrame()
    try:
        df = _download(tickers, years)
    except Exception:
        df = pd.DataFrame()
    for t in [t for t in tickers if t not in df.columns]:        # individual retry
        try:
            one = _download((t,), years)
        except Exception:
            continue
        if t in one.columns:
            df = one[[t]] if df.empty else df.join(one[[t]], how="outer")
    return df.sort_index()


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def _download_range(tickers: tuple, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(list(tickers), start=start, end=end, interval="1d", auto_adjust=True,
                      progress=False, threads=True)
    return _extract_close(raw, tickers)


def get_prices_range(tickers, start: str, end: str) -> pd.DataFrame:
    """Prices between two dates (used for stress tests that reach back before the lookback)."""
    tickers = tuple(sorted({t.upper().strip() for t in tickers}))
    try:
        return _download_range(tickers, start, end)
    except Exception:
        return pd.DataFrame()


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
def validate_ticker(ticker: str):
    """Return (is_valid, latest_price, name). Used to reject unknown tickers."""
    try:
        h = yf.Ticker(ticker).history(period="5d", auto_adjust=True)["Close"].dropna()
        if h.empty:
            return False, None, None
        return True, float(h.iloc[-1]), get_company_info([ticker])[ticker]["name"]
    except Exception:
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
