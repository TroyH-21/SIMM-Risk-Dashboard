# Methodology

All formulas live in `risk_engine.py` (pure functions). All market data comes from Yahoo Finance through `data_fetcher.py`.

## Portfolio returns
- Weights are each holding's value divided by TOTAL portfolio value (positions + cash), using the latest prices.
- Daily portfolio return = sum(weight_i x daily return_i). Today's weights are applied to the whole lookback (a backtest of the
  current portfolio, not the fund's realized performance). Cash earns 0%.
- If a holding has less history than the lookback, the remaining holdings are re-scaled on the days it is missing and the page
  footnotes it.
- Prices are adjusted close. If a ticker has no fresh price, its last stored price is used (clearly flagged) so it is never valued at $0.

## Metrics (N = overlapping trading days, r = daily portfolio return, b = daily benchmark return, rf = annual risk-free rate)
| Metric | Formula |
|---|---|
| Beta | Cov(r, b) / Var(b) (sample covariance) |
| Annualized volatility | Std(r) x sqrt(252) |
| Annualized return | (product of (1 + r))^(252/N) - 1 (geometric, shown separately) |
| Sharpe ratio | (mean(r) x 252 - rf) / annualized volatility |
| Maximum drawdown | Minimum of cumulative value / running peak - 1, starting value counts as a peak; peak and trough dates shown |
| Correlation | Pearson correlation of r and b |
| Tracking error | Std(r - b) x sqrt(252) |
| Information ratio | (portfolio annualized return - benchmark annualized return) / tracking error |
| 1-day 95% VaR | -(5th percentile of r) (historical simulation) |
| 1-day 95% CVaR | -(mean of r on days at or below the 5th percentile) |

Risk-free rate: 3-month T-bill yield (Yahoo `^IRX`), editable in the sidebar, 4% if it cannot be fetched.

## Ex-benchmark view
Portfolios that own their own benchmark (Main Portfolio holds SPY, Maritime Fund holds BOAT) have inflated beta and correlation by
construction. The dashboard re-runs the analysis with that holding removed (remaining weights re-normalized) and shows beta,
correlation and volatility beside the headline numbers.

## Risk contribution (Euler allocation)
With weights w and the covariance matrix S of daily returns: contribution_i = w_i x (S w)_i / sqrt(w' S w). Contributions sum to
portfolio volatility; the dashboard shows each as annualized volatility points and as a share of total risk (top 5).

## Stress tests
For each window in `tags_config.STRESS_WINDOWS`, today's weights are applied to that window's daily returns and compounded. Holdings
without enough history in the window (fewer than 80% of days) are treated as flat, and "coverage" reports the share of invested value
that had data. This is hypothetical, not a forecast.

## Look-through
- Sectors: broad ETFs (QQQ, SPY, IWM) are split across sectors using the spreadsheet's "Sector Diversification" component weights.
- Single names: effective weight = direct weight + sum(ETF weight x constituent weight) using `ETF_TOP_HOLDINGS`. A name is flagged if
  it exceeds 8% effective, or if ETFs add more than 2 percentage points to its direct weight.

## Liquidity
Days to trade = shares / (20% x 20-day average daily volume). Positions above 5 days are flagged.

## Hidden-risk flags
Theme exposure above 25%, return-correlation pairs above 0.85 (broad ETF pairs are shown as expected overlap), foreign revenue above 25%
(China, Taiwan), single stock above 8%, sector above 30%, and an interest-rate sensitivity score from -1 to +1 (rules in `tags_config.py`).

## Assumptions and limitations
- Backtest with today's weights; ignores past trades, fees, taxes and cash flows.
- Reference data in `tags_config.py` (theme tags, regional revenue, ETF constituents, sector maps, stress windows) are maintained
  estimates: review them each semester. They are labeled as estimates in the app.
- Yahoo Finance data can be delayed, revised or briefly unavailable. Company/sector info is stored and refreshed every 30 days.
- Historical VaR/CVaR describe the past distribution of returns and can understate future tail risk.
