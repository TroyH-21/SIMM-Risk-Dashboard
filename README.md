# Fund Risk Dashboard & Pitch Simulator

Streamlit app for our three portfolios (Main Portfolio, Maritime Fund, Family Business Fund).
Page 1 shows portfolio risk vs. SPY; page 2 simulates a Buy/Sell pitch before we make it.

## Files
| File | Purpose |
|---|---|
| `app.py` | Dashboard + Manage Holdings tab |
| `pages/2_Pitch_Analysis.py` | Pitch Simulator |
| `risk_engine.py` | ALL math (pure functions, no Streamlit) |
| `data_fetcher.py` | ALL yfinance calls + caching |
| `db_manager.py` | ALL storage (SQLite or Google Sheets) + one-time seed data |
| `tags_config.py` | Editable theme tags, rate buckets, regional revenue estimates |
| `config.py` | Settings: storage backend, lookbacks, risk limits |
| `ui_components.py` | Shared sidebar, flag banners, formatting |

## (a) Run locally
```
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
First launch creates `fund.db` and fills each portfolio with sample holdings (illustrative share counts).
To remove the samples, delete `SEED_DATA` and the `seed_if_empty()` calls in `db_manager.py`, `app.py`,
and `pages/2_Pitch_Analysis.py`, then delete `fund.db`.

## (b) Optional: Google Sheets storage
1. Go to console.cloud.google.com, create a project, enable the **Google Sheets API** and **Google Drive API**.
2. IAM & Admin -> Service Accounts -> create one -> Keys -> Add key -> JSON. Download it.
3. Create a Google Sheet (e.g. "Fund Data"). Click **Share** and give the service account's `client_email` **Editor** access.
4. Create `.streamlit/secrets.toml` (never commit it; it is in `.gitignore` below):
```toml
[gsheets]
spreadsheet_name = "Fund Data"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```
(Copy each field from the downloaded JSON.)
5. In `config.py` set `STORAGE_BACKEND = "gsheets"` and restart. Worksheets `holdings`, `cash`, `meta` are created automatically
   and seeded once. Use Sheets if you deploy online: SQLite files on Streamlit Cloud are wiped when the app restarts.

## (c) Deploy free on Streamlit Community Cloud
1. Put this folder in a GitHub repo with a `.gitignore` containing `fund.db`, `.streamlit/secrets.toml`, `.venv/`.
2. Go to share.streamlit.io, sign in with GitHub, **New app**, pick the repo, branch, and main file `app.py`.
3. If using Google Sheets: **Advanced settings -> Secrets**, paste the contents of your `secrets.toml`.
4. Deploy, then share the link. Set the app to private and invite members by email if the fund data is sensitive.

## Maintenance notes
- Themes, geographic revenue %, and rate-sensitivity buckets are **your** judgments in `tags_config.py`; review each semester.
- Risk limits (8% stock, 30% sector, 25% theme/region, 0.85 correlation) are in `config.py`.
- If prices stop loading, run `pip install -U yfinance` (Yahoo changes its endpoints; update the pin in requirements.txt).
- Methodology: portfolio returns apply **today's weights** to history; cash earns 0%; adjusted close; Sharpe uses annualized
  geometric return minus the risk-free rate over annualized volatility; beta is covariance/variance vs. SPY.

## Branding
School name, title and colors (St. Bonaventure brown/yellow/white) live at the bottom of `config.py` (`BRAND_SCHOOL`, `BROWN`, `YELLOW`, ...). The Streamlit theme is
`.streamlit/config.toml` (keep its colors in sync). Page styling is in `ui_components.apply_branding()`.

## Sectors
Sector weights follow the fund spreadsheet, not Yahoo. `tags_config.SECTOR_OVERRIDE` holds each ticker's sector from the sheet,
and `ETF_LOOKTHROUGH` splits QQQ/SPY/IWM across sectors using the "Sector Diversification" tab. Tickers not listed fall back to
Yahoo's sector (renamed by `YAHOO_TO_SIMM`). When you buy something new, add it to `SECTOR_OVERRIDE`.

## Benchmarks and picking a sector
- Each portfolio's benchmark is set in `config.py` (`PORTFOLIO_BENCHMARKS`). SPY is the default; the Maritime Fund uses BOAT
  (even though BOAT is also a holding).
- When you add a holding (Manage Holdings tab) or run a pitch that opens a new position, you can pick its sector. Your choice
  overrides the spreadsheet map and Yahoo. Edit the dropdown list in `tags_config.SECTOR_CHOICES`.
- Older `fund.db` files and Google Sheets are upgraded automatically with a `sector` column.

## Risk-free rate and multi-stock pitches (see METHODOLOGY.md for every formula)
- The risk-free rate defaults to the current 3-month T-bill yield (Yahoo symbol ^IRX); if it can't be fetched the app uses 4%.
  You can override it in the sidebar.
- On the Pitch Simulator page, enter every stock pitched that day as a row in the table (Buy/Sell, dollars or shares, optional sector).
  All trades are simulated together; they are applied top to bottom, so a sell placed above a buy can fund it.

## Fund workflow features
- **Record these trades** (Pitch Simulator): updates holdings and cash and logs each trade with your name. See the Trade history table at the
  bottom of the Manage Holdings tab.
- **Save this pitch**: stores the thesis plus before/after beta, volatility, Sharpe and drawdown. Pitch history lists them and lets you add the outcome later.
- **Download meeting summary** (dashboard): a one-page Markdown file for the selected portfolio and lookback. Open it in any text editor,
  paste it into Google Docs, or print it to PDF.
- Last known prices and company/sector info are stored in the database (new tables are created automatically in `fund.db`; with Google
  Sheets the `last_prices`, `company_info`, `trades` and `pitches` worksheets are created automatically).
