"""
Storage layer. EVERY read/write of portfolio data goes through the public
functions at the bottom of this file. The backend (SQLite or Google Sheets)
is chosen by config.STORAGE_BACKEND, so no other file needs to change.
"""
import sqlite3
from contextlib import closing
from datetime import date, datetime

import pandas as pd
import streamlit as st

import config

HOLD_COLS = ["ticker", "shares", "avg_cost", "sector"]
HEADERS = {"holdings": ["portfolio", "ticker", "shares", "avg_cost", "sector"],
           "cash": ["portfolio", "cash"], "meta": ["key", "value"],
           "last_prices": ["ticker", "price", "as_of"],
           "company_info": ["ticker", "name", "sector", "industry", "updated_at"],
           "trades": ["id", "timestamp", "portfolio", "ticker", "side", "shares", "price", "user", "note"],
           "pitches": ["id", "timestamp", "portfolio", "presenter", "thesis", "tickers",
                       "beta_before", "beta_after", "vol_before", "vol_after", "sharpe_before", "sharpe_after",
                       "mdd_before", "mdd_after", "outcome"]}
TRADE_COLS = HEADERS["trades"]
PITCH_COLS = HEADERS["pitches"]


# ------------------------------- SQLite ---------------------------------------
class SQLiteBackend:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as c, c:
            c.execute("CREATE TABLE IF NOT EXISTS holdings(portfolio TEXT, ticker TEXT, "
                      "shares REAL, avg_cost REAL, sector TEXT, PRIMARY KEY(portfolio, ticker))")
            cols = [r[1] for r in c.execute("PRAGMA table_info(holdings)")]
            if "sector" not in cols:      # upgrade older fund.db files
                c.execute("ALTER TABLE holdings ADD COLUMN sector TEXT")
            c.execute("CREATE TABLE IF NOT EXISTS cash(portfolio TEXT PRIMARY KEY, cash REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
            # New tables use IF NOT EXISTS, so an older fund.db is upgraded automatically.
            c.execute("CREATE TABLE IF NOT EXISTS last_prices(ticker TEXT PRIMARY KEY, price REAL, as_of TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS company_info(ticker TEXT PRIMARY KEY, name TEXT, sector TEXT, "
                      "industry TEXT, updated_at TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, "
                      "portfolio TEXT, ticker TEXT, side TEXT, shares REAL, price REAL, \"user\" TEXT, note TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS pitches(id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, "
                      "portfolio TEXT, presenter TEXT, thesis TEXT, tickers TEXT, beta_before REAL, beta_after REAL, "
                      "vol_before REAL, vol_after REAL, sharpe_before REAL, sharpe_after REAL, mdd_before REAL, "
                      "mdd_after REAL, outcome TEXT)")

    def _run(self, sql, args=()):
        with closing(sqlite3.connect(self.path)) as c, c:
            return c.execute(sql, args).fetchall()

    def get_holdings(self, p):
        rows = self._run("SELECT ticker, shares, avg_cost, sector FROM holdings WHERE portfolio=? "
                         "ORDER BY ticker", (p,))
        return pd.DataFrame(rows, columns=HOLD_COLS)

    def upsert_holding(self, p, t, shares, avg_cost, sector=None):
        self._run("INSERT OR REPLACE INTO holdings (portfolio, ticker, shares, avg_cost, sector) "
                  "VALUES (?,?,?,?,?)", (p, t, shares, avg_cost, sector))

    def delete_holding(self, p, t):
        self._run("DELETE FROM holdings WHERE portfolio=? AND ticker=?", (p, t))

    def get_cash(self, p):
        r = self._run("SELECT cash FROM cash WHERE portfolio=?", (p,))
        return float(r[0][0]) if r else 0.0

    def set_cash(self, p, amount):
        self._run("INSERT OR REPLACE INTO cash VALUES (?,?)", (p, amount))

    def get_meta(self, k):
        r = self._run("SELECT value FROM meta WHERE key=?", (k,))
        return r[0][0] if r else None

    def set_meta(self, k, v):
        self._run("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, v))

    # ---- last known prices ----
    def save_last_prices(self, prices):
        with closing(sqlite3.connect(self.path)) as c, c:
            c.executemany("INSERT OR REPLACE INTO last_prices VALUES (?,?,?)",
                          [(t, float(p), date.today().isoformat()) for t, p in prices.items()])

    def get_last_prices(self):
        return {t: (p, a) for t, p, a in self._run("SELECT ticker, price, as_of FROM last_prices")}

    # ---- company info ----
    def get_company_rows(self):
        rows = self._run("SELECT ticker, name, sector, industry, updated_at FROM company_info")
        return {t: {"name": n, "sector": s, "industry": i, "updated_at": u} for t, n, s, i, u in rows}

    def save_company_info(self, records):
        now = datetime.now().isoformat(timespec="seconds")
        with closing(sqlite3.connect(self.path)) as c, c:
            c.executemany("INSERT OR REPLACE INTO company_info VALUES (?,?,?,?,?)",
                          [(r["ticker"], r["name"], r["sector"], r["industry"], now) for r in records])

    # ---- trades / pitches ----
    def add_trade(self, row):
        self._run("INSERT INTO trades (timestamp, portfolio, ticker, side, shares, price, \"user\", note) "
                  "VALUES (?,?,?,?,?,?,?,?)", tuple(row[k] for k in TRADE_COLS[1:]))

    def get_trades(self, portfolio=None):
        q, a = "SELECT * FROM trades", ()
        if portfolio:
            q, a = q + " WHERE portfolio=?", (portfolio,)
        return pd.DataFrame(self._run(q + " ORDER BY id DESC", a), columns=TRADE_COLS)

    def add_pitch(self, row):
        cols = PITCH_COLS[1:]
        self._run(f"INSERT INTO pitches ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                  tuple(row.get(k) for k in cols))

    def get_pitches(self, portfolio=None):
        q, a = "SELECT * FROM pitches", ()
        if portfolio:
            q, a = q + " WHERE portfolio=?", (portfolio,)
        return pd.DataFrame(self._run(q + " ORDER BY id DESC", a), columns=PITCH_COLS)

    def update_pitch_outcome(self, pid, text):
        self._run("UPDATE pitches SET outcome=? WHERE id=?", (text, int(pid)))


# --------------------------- Google Sheets ------------------------------------
class SheetsBackend:
    """Three worksheets (holdings, cash, meta) are created automatically."""

    def __init__(self):
        import gspread
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        self.sh = gc.open(st.secrets["gsheets"]["spreadsheet_name"])
        self.ws = {}
        for name, hdr in HEADERS.items():
            try:
                w = self.sh.worksheet(name)
            except gspread.WorksheetNotFound:
                w = self.sh.add_worksheet(title=name, rows=500, cols=len(hdr))
                w.append_row(hdr)
            self.ws[name] = w
        hdr = self.ws["holdings"].row_values(1)       # upgrade older sheets: add the sector column
        if "sector" not in hdr:
            self.ws["holdings"].update_cell(1, len(hdr) + 1, "sector")

    def _find(self, sheet, keys):
        """Return (sheet row number, row values) of the row whose first columns == keys."""
        for i, r in enumerate(self.ws[sheet].get_all_values()[1:], start=2):
            if [str(x) for x in r[:len(keys)]] == [str(k) for k in keys]:
                return i, r
        return None, None

    def _upsert(self, sheet, keys, row):
        i, _ = self._find(sheet, keys)
        if i:
            self.ws[sheet].update(range_name=f"A{i}:{chr(64 + len(row))}{i}", values=[row])
        else:
            self.ws[sheet].append_row(row)

    def get_holdings(self, p):
        recs = [r for r in self.ws["holdings"].get_all_records() if r["portfolio"] == p]
        df = pd.DataFrame(recs, columns=HEADERS["holdings"])[HOLD_COLS]
        df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
        df["avg_cost"] = pd.to_numeric(df["avg_cost"], errors="coerce")
        df["sector"] = df["sector"].apply(lambda v: v if isinstance(v, str) and v.strip() else None)
        return df.sort_values("ticker").reset_index(drop=True)

    def upsert_holding(self, p, t, shares, avg_cost, sector=None):
        self._upsert("holdings", [p, t], [p, t, shares, "" if avg_cost is None else avg_cost, sector or ""])

    def delete_holding(self, p, t):
        i, _ = self._find("holdings", [p, t])
        if i:
            self.ws["holdings"].delete_rows(i)

    def get_cash(self, p):
        _, r = self._find("cash", [p])
        return float(r[1]) if r and r[1] != "" else 0.0

    def set_cash(self, p, amount):
        self._upsert("cash", [p], [p, amount])

    def get_meta(self, k):
        _, r = self._find("meta", [k])
        return r[1] if r else None

    def set_meta(self, k, v):
        self._upsert("meta", [k], [k, v])

    # ---- last known prices (rewritten in ONE call, and only when a day has passed, to respect API quotas) ----
    def save_last_prices(self, prices):
        today = date.today().isoformat()
        cur = {r["ticker"]: (r["price"], str(r["as_of"])) for r in self.ws["last_prices"].get_all_records()}
        if all(t in cur and cur[t][1] == today for t in prices):
            return
        cur.update({t: (float(p), today) for t, p in prices.items()})
        rows = [[t, p, a] for t, (p, a) in cur.items()]
        self.ws["last_prices"].clear()
        self.ws["last_prices"].update(range_name="A1", values=[HEADERS["last_prices"]] + rows)

    def get_last_prices(self):
        return {r["ticker"]: (float(r["price"]), str(r["as_of"])) for r in self.ws["last_prices"].get_all_records()
                if r["price"] != ""}

    def get_company_rows(self):
        return {r["ticker"]: {"name": r["name"], "sector": r["sector"], "industry": r["industry"],
                              "updated_at": str(r["updated_at"])} for r in self.ws["company_info"].get_all_records()}

    def save_company_info(self, records):
        now = datetime.now().isoformat(timespec="seconds")
        cur = self.get_company_rows()
        for r in records:
            cur[r["ticker"]] = {"name": r["name"], "sector": r["sector"], "industry": r["industry"], "updated_at": now}
        rows = [[t, v["name"], v["sector"], v["industry"], v["updated_at"]] for t, v in cur.items()]
        self.ws["company_info"].clear()
        self.ws["company_info"].update(range_name="A1", values=[HEADERS["company_info"]] + rows)

    def _append_with_id(self, sheet, row):
        n = len(self.ws[sheet].get_all_values())        # header + existing rows -> next id
        self.ws[sheet].append_row([n] + [("" if row.get(k) is None else row.get(k)) for k in HEADERS[sheet][1:]])

    def add_trade(self, row):
        self._append_with_id("trades", row)

    def get_trades(self, portfolio=None):
        recs = [r for r in self.ws["trades"].get_all_records() if not portfolio or r["portfolio"] == portfolio]
        return pd.DataFrame(recs[::-1], columns=TRADE_COLS)

    def add_pitch(self, row):
        self._append_with_id("pitches", row)

    def get_pitches(self, portfolio=None):
        recs = [r for r in self.ws["pitches"].get_all_records() if not portfolio or r["portfolio"] == portfolio]
        return pd.DataFrame(recs[::-1], columns=PITCH_COLS)

    def update_pitch_outcome(self, pid, text):
        i, _ = self._find("pitches", [pid])
        if i:
            self.ws["pitches"].update_cell(i, len(PITCH_COLS), text)


@st.cache_resource
def _backend():
    return SheetsBackend() if config.STORAGE_BACKEND == "gsheets" else SQLiteBackend(config.SQLITE_PATH)


# ------------------------------------------------------------------------------
# ONE-TIME SEED DATA (sample holdings so the app works on first launch).
# To remove: delete SEED_DATA and the seed_if_empty() call at the top of app.py
# and pages/2_Pitch_Analysis.py. All three portfolios are real holdings from the fund spreadsheet.
# ------------------------------------------------------------------------------
SEED_DATA = {
    # Real holdings from the fund spreadsheet (Unrestricted 588 + Endowment 006 combined,
    # lots merged per ticker). Format: "TICKER": (shares, average cost per share).
    "Main Portfolio": {"cash": 109391.56, "holdings": {
        "AAPL": (42, 20.1079),
        "AIQ": (186, 32.2350),
        "AMAT": (10, 173.2000),
        "AMD": (21, 137.7200),
        "AMZN": (83, 204.6619),
        "CB": (50, 212.9100),
        "CEG": (35, 311.0000),
        "CELH": (310, 35.4800),
        "COST": (15, 531.0900),
        "GE": (50, 287.1900),
        "GLD": (149, 171.6955),
        "GNRC": (30, 221.3400),
        "GOOG": (77, 151.1000),
        "HEI": (45, 272.7800),
        "HIMS": (225, 31.2300),
        "HRMY": (250, 32.8200),
        "HYHG": (180, 62.9000),
        "IWM": (137, 73.0830),
        "KCE": (177, 88.8800),
        "LWAY": (690, 21.8600),
        "MCK": (39, 358.4200),
        "META": (12, 724.2700),
        "MS": (58, 149.4154),
        "MSFT": (30, 237.1100),
        "NFG": (88, 79.1900),
        "NVDA": (70, 44.5980),
        "OTTR": (70, 88.9200),
        "QQQ": (121, 37.5426),
        "REMX": (120, 70.2100),
        "RKLB": (250, 3.6600),
        "SCHD": (330, 25.6567),
        "SENEA": (120, 46.2300),
        "SHY": (90, 83.8056),
        "SLQD": (96, 49.9800),
        "SOUN": (350, 8.1200),
        "SPY": (89, 217.1374),
        "TD": (108, 58.3900),
        "TSM": (11, 183.8400),
        "TT": (45, 275.2950),
        "UBER": (100, 31.7600),
        "UGI": (153, 31.7800),
        "USFD": (225, 38.2700),
        "VHT": (82, 236.5600),
        "WS": (240, 32.2800),
        "XEL": (100, 51.0695),
        "XLF": (140, 45.7250),
        "XLI": (50, 131.0700)}},
    # Real holdings from the "Maritime" sheet. Format: "TICKER": (shares, average cost).
    "Maritime Fund": {"cash": 7255.55, "holdings": {
        "KEX": (15, 100.81), "GSL": (100, 21.55), "INSW": (40, 48.23),
        "FRO": (65, 37.95), "BOAT": (57, 55.1366)}},
    # Real holdings from the "Family Business Fund" sheet.
    "Family Business Fund": {"cash": 1750.73, "holdings": {
        "BMWKY": (10, 34.11), "DKS": (3, 138.84), "MAR": (9, 165.15), "WMT": (30, 39.89),
        "HSY": (4, 183.45), "DELL": (5, 166.92), "EPD": (20, 35.945)}},
}


def seed_if_empty():
    b = _backend()
    if b.get_meta("seeded") == "1":
        return
    for p, d in SEED_DATA.items():
        for t, v in d["holdings"].items():
            s, cost = v if isinstance(v, tuple) else (v, None)   # plain number = shares only
            b.upsert_holding(p, t, float(s), cost, None)
        b.set_cash(p, float(d["cash"]))
    b.set_meta("seeded", "1")


# ----------------------------- Public API --------------------------------------
def get_holdings(portfolio):
    return _backend().get_holdings(portfolio)

def save_holding(portfolio, ticker, shares, avg_cost=None, sector=None):
    """sector=None means 'auto' (spreadsheet map, then Yahoo)."""
    _backend().upsert_holding(portfolio, ticker.upper().strip(), float(shares),
                              None if avg_cost is None or pd.isna(avg_cost) else float(avg_cost),
                              sector.strip() if isinstance(sector, str) and sector.strip() else None)

def remove_holding(portfolio, ticker):
    _backend().delete_holding(portfolio, ticker)

def get_cash(portfolio):
    return _backend().get_cash(portfolio)

def save_cash(portfolio, amount):
    _backend().set_cash(portfolio, float(amount))


# --- stale-price fallback, company info cache, trade log, pitch history ---
def save_last_prices(prices: dict):
    if prices:
        _backend().save_last_prices(prices)

def get_last_prices():
    """{ticker: (price, as_of_date_string)}"""
    return _backend().get_last_prices()

def get_company_rows():
    return _backend().get_company_rows()

def save_company_info(records: list):
    if records:
        _backend().save_company_info(records)

def log_trade(portfolio, ticker, side, shares, price, user, note=""):
    _backend().add_trade({"timestamp": datetime.now().isoformat(timespec="seconds"), "portfolio": portfolio,
                          "ticker": ticker, "side": side, "shares": float(shares), "price": float(price),
                          "user": user, "note": note})

def get_trades(portfolio=None):
    return _backend().get_trades(portfolio)

def log_pitch(row: dict):
    """row keys: portfolio, presenter, thesis, tickers, beta/vol/sharpe/mdd _before/_after, outcome."""
    _backend().add_pitch({"timestamp": datetime.now().isoformat(timespec="seconds"), **row})

def get_pitches(portfolio=None):
    return _backend().get_pitches(portfolio)

def set_pitch_outcome(pitch_id, text):
    _backend().update_pitch_outcome(pitch_id, text)
