"""
EDITABLE REFERENCE DATA -- no code knowledge needed, just edit the dictionaries.

How to update:
  * Add a ticker by copying an existing line and changing the ticker/values.
  * Tickers must match Yahoo Finance symbols (e.g. BRK-B, not BRK.B).
  * Review once a semester; geographic numbers are ROUGH estimates from
    company filings (10-K "revenue by geography") and drift over time.
"""

# ---------------------------------------------------------------------------
# 1) THEME TAGS: ticker -> list of themes. A ticker can have several themes.
#    The dashboard flags any theme whose total weight exceeds config.LIMIT_THEME.
# ---------------------------------------------------------------------------
AI = "AI & Semiconductors"
CHINA_TW = "China/Taiwan supply chain"
RATE_GROWTH = "Interest-rate sensitive growth"
ENERGY_T = "Energy transition"

THEME_TAGS = {
    "NVDA": [AI, CHINA_TW], "AVGO": [AI], "AMD": [AI, CHINA_TW], "TSM": [AI, CHINA_TW],
    "MSFT": [AI], "GOOGL": [AI], "GOOG": [AI], "META": [AI], "AMZN": [AI],
    "MU": [AI, CHINA_TW], "ASML": [AI, CHINA_TW], "ARM": [AI], "ORCL": [AI],
    "PLTR": [AI, RATE_GROWTH], "SMCI": [AI, CHINA_TW], "INTC": [AI, CHINA_TW],
    "QCOM": [AI, CHINA_TW], "AAPL": [CHINA_TW], "TSLA": [CHINA_TW, RATE_GROWTH, ENERGY_T],
    "NKE": [CHINA_TW], "BABA": [CHINA_TW], "SHOP": [RATE_GROWTH], "SNOW": [RATE_GROWTH],
    "CRWD": [RATE_GROWTH], "NET": [RATE_GROWTH], "COIN": [RATE_GROWTH], "ROKU": [RATE_GROWTH],
    "ENPH": [ENERGY_T, RATE_GROWTH], "FSLR": [ENERGY_T], "NEE": [ENERGY_T],
    "PLUG": [ENERGY_T, RATE_GROWTH], "ALB": [ENERGY_T], "RIVN": [ENERGY_T, RATE_GROWTH],
}

# ---------------------------------------------------------------------------
# 2) GEOGRAPHIC REVENUE ESTIMATES: ticker -> % of revenue by region.
#    yfinance does NOT provide this. Values are APPROXIMATE (percent, 0-100).
#    Note: Apple reports "Greater China" (incl. Taiwan/HK); we put it under China.
# ---------------------------------------------------------------------------
GEO_REVENUE_PCT = {
    "AAPL": {"China": 17, "Taiwan": 0, "US": 42},
    "NVDA": {"China": 13, "Taiwan": 14, "US": 44},
    "MSFT": {"China": 2, "Taiwan": 0, "US": 50},
    "AMZN": {"China": 0, "Taiwan": 0, "US": 61},
    "GOOGL": {"China": 0, "Taiwan": 0, "US": 49},
    "GOOG": {"China": 0, "Taiwan": 0, "US": 49},
    "META": {"China": 11, "Taiwan": 0, "US": 43},
    "TSM": {"China": 9, "Taiwan": 6, "US": 70},
    "AVGO": {"China": 18, "Taiwan": 6, "US": 31},
    "AMD": {"China": 15, "Taiwan": 3, "US": 30},
    "QCOM": {"China": 46, "Taiwan": 5, "US": 4},
    "INTC": {"China": 29, "Taiwan": 13, "US": 27},
    "MU": {"China": 14, "Taiwan": 8, "US": 56},
    "ASML": {"China": 36, "Taiwan": 15, "US": 10},
    "TSLA": {"China": 22, "Taiwan": 0, "US": 47},
    "NKE": {"China": 15, "Taiwan": 0, "US": 43},
    "BABA": {"China": 85, "Taiwan": 0, "US": 0},
    "JPM": {"China": 1, "Taiwan": 0, "US": 70},
    "XOM": {"China": 3, "Taiwan": 0, "US": 40},
    "JNJ": {"China": 4, "Taiwan": 0, "US": 56},
    "PG": {"China": 7, "Taiwan": 0, "US": 45},
    "KO": {"China": 2, "Taiwan": 0, "US": 40},
    "WMT": {"China": 0, "Taiwan": 0, "US": 85},
    "COST": {"China": 0, "Taiwan": 0, "US": 73},
    "HD": {"China": 0, "Taiwan": 0, "US": 90},
    "V": {"China": 2, "Taiwan": 0, "US": 40},
}
GEO_FOREIGN_REGIONS = ["China", "Taiwan"]   # regions that can trigger the >25% flag

# ---------------------------------------------------------------------------
# 3) INTEREST-RATE SENSITIVITY: +1 = High, 0 = Moderate, -1 = Low/Negative.
#    Order of checks: ticker override -> industry keyword -> sector -> 0.
# ---------------------------------------------------------------------------
RATE_TICKER_OVERRIDE = {"TSLA": 1.0, "PLTR": 1.0, "BRK-B": 0.0}

RATE_INDUSTRY_KEYWORDS = {           # substring of Yahoo "industry" -> score
    "Residential Construction": 1.0,  # homebuilders
    "Banks": -1.0,
    "Insurance": -1.0,
}

RATE_SECTOR_SCORE = {                # Yahoo "sector" -> score
    "Technology": 1.0,               # growth tech
    "Real Estate": 1.0,              # REITs
    "Utilities": 1.0,
    "Energy": -1.0,
    "Financial Services": 0.0,       # only banks/insurers (above) are Low
}


# ---------------------------------------------------------------------------
# 4) SECTORS (taken from the fund spreadsheet's "Sector" column and its
#    "Sector Diversification" tab, so the app matches the sheet).
#    Priority: ETF_LOOKTHROUGH -> SECTOR_OVERRIDE -> Yahoo sector (via YAHOO_TO_SIMM).
#    To add a ticker: copy a line and use one of the fund's sector names.
# ---------------------------------------------------------------------------
SECTOR_OVERRIDE = {
    "AAPL": "Technology",
    "COST": "Consumer Staples",
    "GLD": "Materials",
    "MSFT": "Technology",
    "SCHD": "Financial",
    "SHY": "Fixed Income",
    "UBER": "Technology",
    "HYHG": "Fixed Income",
    "XEL": "Utilities",
    "MCK": "Healthcare",
    "NVDA": "Technology",
    "CB": "Financial",
    "USFD": "Consumer Staples",
    "KCE": "Financial",
    "VHT": "Healthcare",
    "AIQ": "Technology",
    "TT": "Industrials",
    "SENEA": "Consumer Staples",
    "HRMY": "Healthcare",
    "GOOG": "Technology",
    "RKLB": "Technology",
    "WS": "Industrials",
    "TD": "Financial",
    "XLF": "Financial",
    "LWAY": "Consumer Staples",
    "HEI": "Industrials",
    "AMAT": "Technology",
    "AMD": "Technology",
    "TSM": "Technology",
    "SLQD": "Fixed Income",
    "XLI": "Industrials",
    "SOUN": "Technology",
    "NFG": "Utilities",
    "HIMS": "Healthcare",
    "AMZN": "Technology",
    "UGI": "Utilities",
    "REMX": "Materials",
    "GE": "Industrials",
    "CEG": "Utilities",
    "CELH": "Consumer Staples",
    "MS": "Financial",
    "OTTR": "Utilities",
    "META": "Technology",
    "GNRC": "Industrials",
    "BMWKY": "Consumer Discretionary",
    "DKS": "Consumer Discretionary",
    "MAR": "Consumer Discretionary",
    "WMT": "Consumer Staples",
    "HSY": "Consumer Staples",
    "DELL": "Technology",
    "EPD": "Energy",
    "KEX": "Marine Shipping",
    "GSL": "Marine Shipping",
    "INSW": "Energy",
    "FRO": "Energy",
    "BOAT": "Marine Shipping",
}

# Broad ETFs are split across sectors using the component weights on the sheet's
# "Sector Diversification" tab ("Mixed Income Redistribution"). Update them there,
# then copy the numbers here (each ETF's weights should total ~1.0).
ETF_LOOKTHROUGH = {
    "IWM": {"Technology": 0.1651, "Consumer Staples": 0.0188, "Materials": 0.106, "Financial": 0.225, "Healthcare": 0.1712, "Utilities": 0.0299, "Industrials": 0.1918, "Fixed Income": 0.0922},
    "QQQ": {"Technology": 0.549, "Financial": 0.15, "Healthcare": 0.0992, "Industrials": 0.0809, "Consumer Staples": 0.0494, "Materials": 0.0459, "Utilities": 0.0239, "Fixed Income": 0.0017},
    "SPY": {"Technology": 0.49, "Consumer Staples": 0.1, "Materials": 0.052, "Financial": 0.148, "Healthcare": 0.094, "Utilities": 0.022, "Industrials": 0.094, "Fixed Income": 0.0},
}

# Used only for tickers NOT listed above (e.g. a new pitch): converts Yahoo's sector
# names to the fund's names. Matches the sheet: Energy -> Energy, REITs -> Financial,
# Communication Services -> Technology.
YAHOO_TO_SIMM = {
    "Financial Services": "Financial",
    "Real Estate": "Financial",
    "Communication Services": "Technology",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
}

# Sector choices shown in the "Add holding" and "Pitch" dropdowns. Add your own names here.
SECTOR_CHOICES = sorted(set(SECTOR_OVERRIDE.values()) | {"Financial", "Healthcare", "Real Estate", "Consumer Discretionary",
                                                          "Consumer Staples", "Industrials", "Materials", "Technology",
                                                          "Utilities", "Energy", "Fixed Income"})


# ---------------------------------------------------------------------------
# 5) ETF TOP HOLDINGS (single-name look-through). ROUGH ESTIMATES -- refresh each semester
#    from the fund factsheets (issuer websites list top 10 holdings and weights).
#    Format: ETF -> {constituent ticker: weight as a fraction of that ETF}.
#    The app adds ETF weight x constituent weight to each stock's direct weight.
# ---------------------------------------------------------------------------
ETF_TOP_HOLDINGS = {
    "SPY": {"NVDA": 0.075, "MSFT": 0.065, "AAPL": 0.065, "AMZN": 0.040, "META": 0.030,
            "AVGO": 0.025, "GOOGL": 0.020, "GOOG": 0.017, "TSLA": 0.017, "BRK-B": 0.016},
    "QQQ": {"NVDA": 0.090, "MSFT": 0.080, "AAPL": 0.080, "AMZN": 0.055, "AVGO": 0.050,
            "META": 0.035, "TSLA": 0.030, "GOOGL": 0.028, "GOOG": 0.026, "COST": 0.026},
    "SCHD": {"KO": 0.043, "CVX": 0.042, "PEP": 0.042, "CSCO": 0.042, "ABBV": 0.042,
             "HD": 0.040, "AMGN": 0.040, "VZ": 0.040, "LMT": 0.040, "TXN": 0.038},
    "XLF": {"BRK-B": 0.130, "JPM": 0.100, "V": 0.080, "MA": 0.065, "BAC": 0.045,
            "WFC": 0.035, "GS": 0.030, "MS": 0.025, "AXP": 0.025, "SPGI": 0.022},
    "VHT": {"LLY": 0.120, "JNJ": 0.070, "UNH": 0.060, "ABBV": 0.060, "MRK": 0.045,
            "TMO": 0.040, "ABT": 0.040, "ISRG": 0.035, "AMGN": 0.030, "DHR": 0.030},
    "KCE": {"MS": 0.030, "GS": 0.030, "SCHW": 0.030, "BX": 0.030, "KKR": 0.030,
            "APO": 0.030, "IBKR": 0.030, "RJF": 0.030, "HOOD": 0.030, "COIN": 0.030},
}

# ---------------------------------------------------------------------------
# 6) STRESS WINDOWS: label -> (start date, end date), YYYY-MM-DD.
#    The dashboard applies TODAY'S weights to each window's historical daily returns.
#    Add a window by copying a line. Holdings that did not exist yet are footnoted.
# ---------------------------------------------------------------------------
STRESS_WINDOWS = {
    "Mar 2020 crash (2020-02-19 to 2020-03-23)": ("2020-02-19", "2020-03-23"),
    "2022 drawdown (2022-01-03 to 2022-10-14)": ("2022-01-03", "2022-10-14"),
}
