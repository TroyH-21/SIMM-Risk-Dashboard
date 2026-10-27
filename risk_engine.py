"""
Every calculation lives here as a pure function (no Streamlit, no network).
Weights are fractions of TOTAL portfolio value (positions + cash), so cash
shows up as its own slice and all weights sum to 100%.
Portfolio returns apply TODAY'S weights to historical returns; cash earns 0%.
"""
import numpy as np
import pandas as pd

import config
import tags_config

TD = config.TRADING_DAYS
POS_COLS = ["ticker", "name", "sector", "industry", "shares", "avg_cost", "price", "value", "weight"]


# ------------------------------ positions -------------------------------------
def latest_prices(prices: pd.DataFrame) -> pd.Series:
    return prices.ffill().iloc[-1].dropna() if not prices.empty else pd.Series(dtype=float)


MULTI = "Multi-sector ETF"


def resolve_sector(ticker, yahoo_sector, user_sector=None):
    """Sector: user's choice > look-through ETF > spreadsheet override > Yahoo (renamed)."""
    if isinstance(user_sector, str) and user_sector.strip():
        return user_sector.strip()
    if ticker in tags_config.ETF_LOOKTHROUGH:
        return MULTI
    if ticker in tags_config.SECTOR_OVERRIDE:
        return tags_config.SECTOR_OVERRIDE[ticker]
    y = yahoo_sector or "Unknown"
    return tags_config.YAHOO_TO_SIMM.get(y, y)


def build_positions(holdings, cash, latest, info):
    rows = []
    for _, h in holdings.iterrows():
        t = h["ticker"]
        px = latest.get(t, np.nan)
        meta = info.get(t, {})
        rows.append({"ticker": t, "name": meta.get("name", t),
                     "sector": resolve_sector(t, meta.get("sector"), h.get("sector")), "industry": meta.get("industry") or "",
                     "shares": float(h["shares"]), "avg_cost": h.get("avg_cost", np.nan), "price": px,
                     "value": float(h["shares"]) * px if pd.notna(px) else 0.0})
    df = pd.DataFrame(rows, columns=POS_COLS[:-1])
    total = df["value"].sum() + cash
    df["weight"] = df["value"] / total if total > 0 else 0.0
    return df.sort_values("value", ascending=False).reset_index(drop=True), float(total)


def sector_table(positions, cash, total) -> pd.Series:
    """Weight by sector; unknown-sector tickers go in 'Unknown', cash in 'Cash'."""
    acc = {}
    for _, r in positions.iterrows():
        lt = tags_config.ETF_LOOKTHROUGH.get(r["ticker"]) if r["sector"] == MULTI else None
        if lt:                                  # split a broad ETF across its sectors
            tot = sum(lt.values())
            for sec, w in lt.items():
                acc[sec] = acc.get(sec, 0.0) + r["weight"] * w / tot
        else:
            acc[r["sector"]] = acc.get(r["sector"], 0.0) + r["weight"]
    if total > 0 and cash > 0:
        acc["Cash"] = cash / total
    return pd.Series(acc, dtype=float).sort_values(ascending=False)


# ------------------------------ returns & metrics ------------------------------
def portfolio_returns(weights: pd.Series, rets: pd.DataFrame) -> pd.Series:
    """Daily portfolio return from fixed weights. If a holding has no data yet on a
    date (short history), the remaining holdings are re-scaled so nothing crashes."""
    cols = [t for t in weights.index if t in rets.columns and weights[t] > 0]
    if not cols:
        return pd.Series(dtype=float)
    w, r = weights[cols], rets[cols]
    avail_w = r.notna().mul(w, axis=1).sum(axis=1)
    num = r.fillna(0).mul(w, axis=1).sum(axis=1)
    out = (num / avail_w.where(avail_w > 0)) * w.sum()
    return out.dropna()


def compute_metrics(port: pd.Series, bench: pd.Series, rf: float):
    df = pd.concat([port.rename("p"), bench.rename("b")], axis=1).dropna()
    n = len(df)
    if n < 30:
        return None
    p, b = df["p"], df["b"]
    vol = p.std(ddof=1) * np.sqrt(TD)
    ann_ret = (1 + p).prod() ** (TD / n) - 1              # geometric (compounded) return, shown as its own metric
    bench_ann = (1 + b).prod() ** (TD / n) - 1
    mean_ann = p.mean() * TD                               # arithmetic, used in Sharpe
    te = (p - b).std(ddof=1) * np.sqrt(TD)
    cum = (1 + p).cumprod()
    peak = np.maximum(cum.cummax(), 1.0)
    dd = cum / peak - 1
    trough = dd.idxmin()
    pk = cum.loc[:trough].idxmax()
    q = float(np.percentile(p, config.VAR_PROB * 100))     # 5th percentile daily return
    tail = p[p <= q]
    return {"beta": float(np.cov(p, b, ddof=1)[0, 1] / b.var(ddof=1)), "vol": float(vol),
            "ann_return": float(ann_ret), "mean_ann": float(mean_ann),
            "sharpe": float((mean_ann - rf) / vol) if vol > 0 else np.nan,
            "tracking_error": float(te),
            "info_ratio": float((ann_ret - bench_ann) / te) if te > 1e-12 else np.nan,
            "var95": float(-q), "cvar95": float(-tail.mean()) if len(tail) else float(-q),
            "max_dd": float(dd.min()), "dd_peak": pk if cum.loc[pk] >= 1 else df.index[0],
            "dd_trough": trough, "corr": float(p.corr(b)), "n_days": n,
            "start": df.index[0], "end": df.index[-1]}


def cumulative_index(r: pd.Series) -> pd.Series:
    return 100 * (1 + r).cumprod()


# ------------------------------ hidden-risk flags ------------------------------
def theme_exposure(positions, tags=tags_config.THEME_TAGS):
    out = {}
    for _, r in positions.iterrows():
        for th in tags.get(r["ticker"], []):
            d = out.setdefault(th, {"weight": 0.0, "tickers": []})
            d["weight"] += r["weight"]
            d["tickers"].append(r["ticker"])
    return out


def find_clusters(rets, tickers, threshold=config.CORR_CLUSTER):
    cols = [t for t in tickers if t in rets.columns]
    if len(cols) < 2:
        return []
    c = rets[cols].corr(min_periods=60)
    pairs = [(a, b, float(c.loc[a, b])) for i, a in enumerate(cols) for b in cols[i + 1:]
             if pd.notna(c.loc[a, b]) and c.loc[a, b] > threshold]
    return sorted(pairs, key=lambda x: -x[2])


def geo_exposure(positions, geo=tags_config.GEO_REVENUE_PCT):
    """Revenue-weighted exposure across holdings that have estimates."""
    covered = positions[positions["ticker"].isin(geo)]
    invested = positions["value"].sum()
    cov_val = covered["value"].sum()
    regions = {}
    for reg in ["China", "Taiwan", "US"]:
        regions[reg] = (sum(r["value"] * geo[r["ticker"]].get(reg, 0) / 100 for _, r in covered.iterrows())
                        / cov_val) if cov_val > 0 else np.nan
    return {"regions": regions, "coverage": cov_val / invested if invested > 0 else 0.0,
            "missing": [t for t in positions["ticker"] if t not in geo]}


def rate_score(ticker, sector, industry):
    if ticker in tags_config.RATE_TICKER_OVERRIDE:
        return tags_config.RATE_TICKER_OVERRIDE[ticker]
    for kw, s in tags_config.RATE_INDUSTRY_KEYWORDS.items():
        if kw.lower() in (industry or "").lower():
            return s
    return tags_config.RATE_SECTOR_SCORE.get(sector, 0.0)


def rate_label(score):
    if score >= 0.5: return "High"
    if score >= 0.2: return "Moderately High"
    if score > -0.2: return "Moderate"
    if score > -0.5: return "Moderately Low"
    return "Low"


def rate_sensitivity(positions):
    """Weighted score in [-1, +1] (cash counts as 0). 'pressured' = share of portfolio scored High."""
    def _score(r):
        lt = tags_config.ETF_LOOKTHROUGH.get(r["ticker"]) if r["sector"] == MULTI else None
        if lt:
            return sum(w * tags_config.RATE_SECTOR_SCORE.get(s, 0.0) for s, w in lt.items()) / sum(lt.values())
        return rate_score(r["ticker"], r["sector"], r["industry"])
    sc = positions.apply(_score, axis=1)
    score = float((sc * positions["weight"]).sum()) if len(positions) else 0.0
    return {"score": score, "label": rate_label(score),
            "pressured": float((sc.clip(lower=0) * positions["weight"]).sum()) if len(positions) else 0.0}


def concentration_flags(positions, sectors):
    flags = [{"kind": "stock", "name": r["ticker"], "weight": r["weight"], "limit": config.LIMIT_SINGLE_STOCK}
             for _, r in positions.iterrows() if r["weight"] > config.LIMIT_SINGLE_STOCK + 1e-9]
    flags += [{"kind": "sector", "name": s, "weight": w, "limit": config.LIMIT_SECTOR}
              for s, w in sectors.items() if s not in ("Cash", "Unknown") and w > config.LIMIT_SECTOR + 1e-9]
    return flags


# ------------------------------ full analysis ----------------------------------
def analyze(holdings, cash, prices, info, rf, bench=config.BENCHMARK, exclude=None, fallback_prices=None):
    """exclude: ticker to drop from holdings (used for the ex-benchmark view).
    fallback_prices: {ticker: last known price}, used ONLY when a holding has no fresh price."""
    if exclude:
        holdings = holdings[holdings["ticker"] != exclude].reset_index(drop=True)
    latest = latest_prices(prices).copy()
    stale = []
    for t, px_ in (fallback_prices or {}).items():
        if t not in latest.index and t in set(holdings["ticker"]):
            latest[t] = float(px_)
            stale.append(t)
    positions, total = build_positions(holdings, cash, latest, info)
    sectors = sector_table(positions, cash, total)
    out = {"positions": positions, "total": total, "cash": cash, "sectors": sectors, "rf": rf,
           "missing_price": [t for t in positions["ticker"] if t not in latest.index],
           "metrics": None, "bench_metrics": None, "notes": [], "stale": stale}
    rets = prices.ffill(limit=5).pct_change(fill_method=None).iloc[1:] if not prices.empty else pd.DataFrame()
    out["rets"] = rets
    out["themes"] = theme_exposure(positions)
    out["geo"] = geo_exposure(positions)
    out["rate"] = rate_sensitivity(positions)
    out["concentration"] = concentration_flags(positions, sectors)
    out["clusters"] = find_clusters(rets, list(positions["ticker"]))
    if bench not in rets.columns or positions.empty:
        return out
    port = portfolio_returns(positions.set_index("ticker")["weight"], rets)
    b = rets[bench].dropna()
    out["port_ret"], out["bench_ret"] = port, b
    out["metrics"] = compute_metrics(port, b, rf)
    bb = b.loc[b.index.intersection(port.index)]
    out["bench_metrics"] = compute_metrics(bb, bb, rf)
    first = prices.apply(lambda s: s.first_valid_index())
    start = prices.index[0]
    out["notes"] = [f"{t} has price history only from {first[t]:%Y-%m-%d}; earlier days use the other holdings."
                    for t in positions["ticker"]
                    if t in first.index and pd.notna(first[t]) and (first[t] - start).days > 7]
    return out


# ------------------------------ pitch simulation -------------------------------
def validate_trade(holdings, cash, ticker, side, shares, price):
    """Return (ok, message, is_new_position)."""
    held = holdings.set_index("ticker")["shares"].to_dict()
    cur = held.get(ticker, 0.0)
    if not shares or shares <= 0:
        return False, "Enter an amount greater than zero.", False
    if side == "Sell":
        if ticker not in held:
            return False, f"You can't sell {ticker}: it isn't held in this portfolio.", False
        if shares > cur + 1e-9:
            return False, f"Can't sell {shares:,.4f} shares of {ticker}; the portfolio only holds {cur:,.4f}.", False
    else:
        cost = shares * price
        if cost > cash + 1e-6:
            return False, f"This buy costs ${cost:,.2f} but only ${cash:,.2f} of cash is available.", False
    return True, "", ticker not in held


def simulate_trade(holdings, cash, ticker, side, shares, price, sector=None):
    h = holdings.copy()
    if "sector" not in h.columns:
        h["sector"] = None
    if side == "Buy":
        if ticker in set(h["ticker"]):
            i = h.index[h["ticker"] == ticker][0]
            old_s, old_c = h.at[i, "shares"], h.at[i, "avg_cost"]
            h.at[i, "avg_cost"] = ((old_s * old_c + shares * price) / (old_s + shares)
                                   if pd.notna(old_c) else np.nan)
            h.at[i, "shares"] = old_s + shares
        else:
            h.loc[len(h)] = [ticker, shares, price, sector]
        return h, cash - shares * price
    i = h.index[h["ticker"] == ticker][0]
    h.at[i, "shares"] -= shares
    h = h[h["shares"] > 1e-9].reset_index(drop=True)
    return h, cash + shares * price


def pitch_correlations(ticker, positions, rets, n=5):
    top = positions[positions["ticker"] != ticker].head(n)
    rows = []
    for _, r in top.iterrows():
        c = rets[ticker].corr(rets[r["ticker"]]) if ticker in rets and r["ticker"] in rets else np.nan
        rows.append({"Holding": r["ticker"], "Weight": r["weight"], "Correlation": c})
    return pd.DataFrame(rows, columns=["Holding", "Weight", "Correlation"])


def comparison_rows(a0, a1, ticker, bench=config.BENCHMARK):
    """Before/After rows with plain-English readouts. kind: num | pct | usd."""
    m0, m1 = a0["metrics"] or {}, a1["metrics"] or {}
    nan = np.nan

    tickers = [ticker] if isinstance(ticker, str) else list(dict.fromkeys(ticker))

    def w(a, t):
        r = a["positions"].loc[a["positions"]["ticker"] == t, "weight"]
        return float(r.iloc[0]) if len(r) else 0.0

    def g(m, k): return m.get(k, nan)
    rows = []

    def add(name, kind, b, a, text):
        rows.append({"metric": name, "kind": kind, "before": b, "after": a,
                     "change": a - b if pd.notna(a) and pd.notna(b) else nan, "text": text})

    b, a = g(m0, "beta"), g(m1, "beta")
    t = "n/a (not enough history)"
    if pd.notna(a) and pd.notna(b):
        pct = (a / b - 1) * 100 if b else 0
        t = ("Beta is essentially unchanged." if abs(a - b) < 0.005 else
             f"Beta {'rises' if a > b else 'falls'} {b:.2f} → {a:.2f}: the portfolio becomes "
             f"~{abs(pct):.0f}% {'more' if a > b else 'less'} sensitive to market moves.")
    add("Beta", "num", b, a, t)
    b, a = g(m0, "vol"), g(m1, "vol")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Volatility {'rises' if a > b else 'falls'} {b:.2%} → {a:.2%}: day-to-day swings get "
        f"{'larger' if a > b else 'smaller'}.")
    add("Annualized Volatility", "pct", b, a, t)
    b, a = g(m0, "sharpe"), g(m1, "sharpe")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Sharpe {'improves' if a > b else 'worsens'} {b:.2f} → {a:.2f}: "
        f"{'more' if a > b else 'less'} historical return per unit of risk.")
    add("Sharpe Ratio", "num", b, a, t)
    b, a = g(m0, "max_dd"), g(m1, "max_dd")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Worst historical drop would have been {'deeper' if a < b else 'shallower'}: {b:.2%} → {a:.2%}.")
    add("Maximum Drawdown", "pct", b, a, t)
    b, a = g(m0, "tracking_error"), g(m1, "tracking_error")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Tracking error {'rises' if a > b else 'falls'} {b:.2%} → {a:.2%}: returns deviate "
        f"{'more' if a > b else 'less'} from {bench}.")
    add("Tracking Error", "pct", b, a, t)
    b, a = g(m0, "info_ratio"), g(m1, "info_ratio")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Information ratio {'improves' if a > b else 'worsens'} {b:.2f} → {a:.2f}: "
        f"{'more' if a > b else 'less'} excess return vs. {bench} per unit of tracking error.")
    add("Information Ratio", "num", b, a, t)
    b, a = g(m0, "corr"), g(m1, "corr")
    t = "n/a" if pd.isna(a) or pd.isna(b) else (
        f"Portfolio moves {'more' if a > b else 'less'} in lockstep with {bench} ({b:.2f} → {a:.2f}).")
    add(f"Correlation to {bench}", "num", b, a, t)
    add("Cash Remaining", "usd", a0["cash"], a1["cash"],
        f"Cash {'increases' if a1['cash'] > a0['cash'] else 'decreases'} by ${abs(a1['cash'] - a0['cash']):,.2f}.")
    for t in tickers:
        add(f"{t} Weight", "pct", w(a0, t), w(a1, t),
            f"{t} goes from {w(a0, t):.2%} to {w(a1, t):.2%} of total portfolio value.")
    return rows


def drawdown_series(r: pd.Series) -> pd.Series:
    """Underwater curve: % below the running peak (starting value counts as a peak)."""
    cum = (1 + r).cumprod()
    return cum / np.maximum(cum.cummax(), 1.0) - 1


def apply_trades(holdings, cash, trades):
    """Apply several pitched trades IN ORDER (so an earlier sell can fund a later buy).
    trades: dicts with ticker, side, shares, price, sector. Returns (holdings, cash, errors, log)."""
    h, c, errors, log = holdings.copy(), cash, [], []
    for i, t in enumerate(trades, 1):
        ok, msg, is_new = validate_trade(h, c, t["ticker"], t["side"], t["shares"], t["price"])
        if not ok:
            errors.append(f"Trade {i} ({t['side']} {t['ticker']}): {msg}")
            continue
        h, c = simulate_trade(h, c, t["ticker"], t["side"], t["shares"], t["price"], t.get("sector") if is_new else None)
        log.append({**t, "new": is_new})
    return h, c, errors, log


def pitch_corr_matrix(tickers, positions, rets, n=5):
    """Correlation of each pitched ticker (rows) with the top-n existing holdings (columns)."""
    top = [x for x in positions["ticker"] if x not in tickers][:n]
    return pd.DataFrame({h: [rets[t].corr(rets[h]) if t in rets.columns and h in rets.columns else np.nan
                             for t in tickers] for h in top}, index=list(tickers))


# ------------------------------ C-section analytics ----------------------------
def risk_contributions(weights: pd.Series, rets: pd.DataFrame, top=5) -> pd.DataFrame:
    """Euler risk allocation: contribution_i = w_i * (Cov w)_i / portfolio vol.
    Returns annualized vol points per holding and its share of total risk."""
    cols = [t for t in weights.index if t in rets.columns and weights[t] > 0]
    empty = pd.DataFrame(columns=["ticker", "weight", "contribution", "pct"])
    if not cols:
        return empty
    w = weights[cols].values.astype(float)
    cov = rets[cols].cov(min_periods=60).fillna(0).values
    var = float(w @ cov @ w)
    if var <= 0:
        return empty
    sig = np.sqrt(var)
    contrib = w * (cov @ w) / sig
    df = pd.DataFrame({"ticker": cols, "weight": w, "contribution": contrib * np.sqrt(TD), "pct": contrib / sig})
    return df.sort_values("pct", ascending=False).head(top).reset_index(drop=True)


def stress_test(weights: pd.Series, rets: pd.DataFrame, bench: str, start: str, end: str):
    """Apply today's weights to a historical window. Holdings without history for the window
    are treated as flat (0%) and reported through `coverage`."""
    win = rets.loc[start:end]
    invested = float(weights.sum())
    if win.empty or invested <= 0:
        return None
    cols = [t for t in weights.index if t in win.columns and win[t].notna().mean() >= 0.8]
    if not cols:
        return {"ret": np.nan, "bench_ret": np.nan, "coverage": 0.0, "days": 0}
    p = portfolio_returns(weights[cols], win[cols])
    b = win[bench].dropna() if bench in win.columns else pd.Series(dtype=float)
    return {"ret": float((1 + p).prod() - 1), "bench_ret": float((1 + b).prod() - 1) if len(b) else np.nan,
            "coverage": float(weights[cols].sum() / invested), "days": int(len(p))}


def effective_weights(positions: pd.DataFrame, etf_top=tags_config.ETF_TOP_HOLDINGS):
    """Direct weight + sum(ETF weight x constituent weight). Returns ({ticker: effective}, flags)."""
    direct = positions.set_index("ticker")["weight"].to_dict()
    eff = dict(direct)
    for etf, cons in etf_top.items():
        w = direct.get(etf, 0.0)
        for t, cw in cons.items():
            if w > 0:
                eff[t] = eff.get(t, 0.0) + w * cw
    funds = set(tags_config.ETF_LOOKTHROUGH) | set(etf_top)
    flags = []
    for t, e in sorted(eff.items(), key=lambda x: -x[1]):
        if t in funds:
            continue
        d = direct.get(t, 0.0)
        if e > config.LIMIT_SINGLE_STOCK + 1e-9:
            flags.append({"name": t, "direct": d, "effective": e, "reason": f"above the {config.LIMIT_SINGLE_STOCK:.0%} single-stock limit"})
        elif e - d > config.LIMIT_EFFECTIVE_DELTA + 1e-9:
            flags.append({"name": t, "direct": d, "effective": e,
                          "reason": f"ETFs add {(e - d) * 100:.1f} pp to the direct weight"})
    return eff, flags


def days_to_trade(positions: pd.DataFrame, adv: dict) -> dict:
    """shares / (participation x average daily volume); NaN when volume is unknown."""
    out = {}
    for _, r in positions.iterrows():
        v = adv.get(r["ticker"])
        out[r["ticker"]] = r["shares"] / (config.LIQUIDITY_PARTICIPATION * v) if v and v > 0 else np.nan
    return out


def liquidity_flags(days: dict):
    return sorted([(t, d) for t, d in days.items() if pd.notna(d) and d > config.LIQUIDITY_DAYS_FLAG], key=lambda x: -x[1])
