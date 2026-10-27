"""Central settings. Change values here, not in the other files."""

# --- Storage -----------------------------------------------------------------
# "sqlite"  -> local file fund.db (default; created automatically)
# "gsheets" -> Google Sheets (needs credentials in Streamlit secrets, see README)
STORAGE_BACKEND = "sqlite"
SQLITE_PATH = "fund.db"

# --- Portfolios / market data -------------------------------------------------
PORTFOLIOS = ["Main Portfolio", "Maritime Fund", "Family Business Fund"]
BENCHMARK = "SPY"                               # default benchmark
PORTFOLIO_BENCHMARKS = {"Maritime Fund": "BOAT"}  # per-portfolio overrides (BOAT is also a holding)


def benchmark_for(portfolio):
    return PORTFOLIO_BENCHMARKS.get(portfolio, BENCHMARK)

LOOKBACK_OPTIONS = {"1Y": 1, "3Y": 3, "5Y": 5}   # label -> years
DEFAULT_LOOKBACK = "3Y"
TRADING_DAYS = 252
FALLBACK_RF = 0.04          # used if ^IRX (3-month T-bill) cannot be fetched
CACHE_TTL = 3600            # seconds (1 hour) for price downloads

# --- Risk limits (used by the warning banners) ---------------------------------
LIMIT_SINGLE_STOCK = 0.08   # 8% of total portfolio value
LIMIT_SECTOR = 0.30         # 30%
LIMIT_THEME = 0.25          # 25%
LIMIT_REGION = 0.25         # 25% foreign revenue exposure
CORR_CLUSTER = 0.85         # pair correlation that counts as a "hidden cluster"

# --- Extra analytics settings -------------------------------------------------
LIMIT_EFFECTIVE_DELTA = 0.02     # flag a name if ETF look-through adds more than 2 pp to its direct weight
VAR_PROB = 0.05                  # 1-day 95% VaR/CVaR
LIQUIDITY_PARTICIPATION = 0.20   # assume we can trade 20% of average daily volume
LIQUIDITY_DAYS_FLAG = 5          # warn if a position takes longer than this many days to trade
COMPANY_INFO_MAX_AGE_DAYS = 30   # refresh stored company/sector info after this long

# --- Branding (change these to rebrand the whole app) ---------------------------
BRAND_SCHOOL = "St. Bonaventure University"
BRAND_NAME = "Students in Money Management"
BRAND_TAGLINE = "Portfolio Risk & Pitch Analysis"
BROWN = "#4B2615"        # main
BROWN_MID = "#7A4A2B"
YELLOW = "#F5B800"       # accent
CREAM = "#F7F2EA"        # soft background
BORDER = "#E6DCCB"
COLORWAY = [BROWN, YELLOW, "#9C7A5B", "#C9B28F", "#2E7D5B", "#B5651D"]
SECTOR_COLORS = ["#4B2615", "#F5B800", "#8C5A35", "#D9A441", "#A67C52", "#C9B28F",
                 "#6B7F5E", "#7A8B99", "#B5651D", "#E8D5A8"]
