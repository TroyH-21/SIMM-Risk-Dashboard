"""Main page: portfolio overview & risk dashboard."""
import pandas as pd
import plotly.express as px
import streamlit as st

import config, data_fetcher, db_manager, risk_engine, tags_config, ui_components as ui

st.set_page_config(page_title=f"{config.BRAND_NAME} | Dashboard", layout="wide")
ui.apply_branding()
db_manager.seed_if_empty()          # one-time sample data (see db_manager.SEED_DATA to remove)
ctx = ui.sidebar_controls()
P, LB, BM = ctx["portfolio"], ctx["lookback"], ctx["benchmark"]

holdings, cash = db_manager.get_holdings(P), db_manager.get_cash(P)
hero = st.empty()
HERO = dict(title=P, subtitle=f"{config.BRAND_NAME} · Portfolio risk dashboard", eyebrow="Portfolio Overview",
            chips=[f"Benchmark: {BM}", f"Lookback: {LB}", f"Risk-free rate (3-month T-bill): {ctx['rf']:.2%}"], slot=hero)
ui.page_header(**HERO)
tab_dash, tab_manage = st.tabs(["Risk Dashboard", "Manage Holdings"])

# ------------------------------ Manage Holdings -------------------------------
with tab_manage:
    st.subheader("Add a holding")
    with st.form("add"):
        c = st.columns(4)
        t_in = c[0].text_input("Ticker (e.g. AAPL)")
        s_in = c[1].text_input("Shares")
        c_in = c[2].text_input("Average cost per share (optional)")
        sec_in = c[3].selectbox("Sector", ui.sector_options(ui.AUTO),
                                help="Choose the sector this stock counts toward. Edit the list in tags_config.py.")
        if st.form_submit_button("Add holding"):
            t = t_in.upper().strip()
            s, e1 = ui.parse_number(s_in, "Shares")
            cost, e2 = ui.parse_number(c_in, "Average cost", allow_blank=True)
            ok, _, _ = data_fetcher.validate_ticker(t) if t else (False, None, None)
            if not t: st.error("Please enter a ticker.")
            elif e1 or e2: st.error(e1 or e2)
            elif s == 0: st.error("Shares must be greater than zero.")
            elif t in set(holdings["ticker"]): st.error(f"{t} is already held. Use 'Edit a holding' below.")
            elif not ok: st.error(f"We couldn't find market data for '{t}'. Check the ticker symbol.")
            else:
                db_manager.save_holding(P, t, s, cost, ui.sector_value(sec_in)); st.rerun()
    if len(holdings):
        st.subheader("Edit a holding")
        with st.form("edit"):
            c = st.columns(4)
            et = c[0].selectbox("Ticker", list(holdings["ticker"]))
            es = c[1].text_input("New shares")
            ec = c[2].text_input("New average cost (blank = keep current)")
            esec = c[3].selectbox("Sector", ui.sector_options(ui.KEEP))
            if st.form_submit_button("Save changes"):
                s, e1 = ui.parse_number(es, "Shares")
                cost, e2 = ui.parse_number(ec, "Average cost", allow_blank=True)
                cur = holdings.set_index("ticker").loc[et]
                if e1 or e2: st.error(e1 or e2)
                elif s == 0: st.error("Shares must be greater than zero (use Remove to delete a holding).")
                else:
                    db_manager.save_holding(P, et, s, cur["avg_cost"] if cost is None else cost,
                                            ui.sector_value(esec) or cur["sector"]); st.rerun()
        st.subheader("Remove a holding")
        with st.form("remove"):
            rt = st.selectbox("Ticker to remove", list(holdings["ticker"]))
            if st.form_submit_button("Remove"):
                db_manager.remove_holding(P, rt); st.rerun()
    st.subheader("Cash balance")
    with st.form("cash"):
        cash_in = st.text_input("Cash ($)", value=f"{cash:.2f}")
        if st.form_submit_button("Update cash"):
            v, e = ui.parse_number(cash_in, "Cash")
            if e: st.error(e)
            else:
                db_manager.save_cash(P, v); st.rerun()

    st.subheader("Trade history")
    tr = db_manager.get_trades(P)
    if tr.empty:
        st.caption("No trades recorded yet. Use 'Record these trades' on the Pitch Simulator page.")
    else:
        ui.html_table(pd.DataFrame({"Date": tr["timestamp"].astype(str).str.replace("T", " "), "Ticker": tr["ticker"],
                                    "Side": tr["side"], "Shares": tr["shares"].map("{:,.4f}".format),
                                    "Price": tr["price"].map("${:,.2f}".format), "Recorded by": tr["user"],
                                    "Note": tr["note"].fillna("")}), right=("Shares", "Price"))


# ------------------------------ Dashboard -------------------------------------
with tab_dash:
    if holdings.empty:
        st.info("This portfolio has no holdings yet. Add one in the 'Manage Holdings' tab.")
        st.stop()
    held = list(holdings["ticker"])
    tickers = held + [BM]
    with st.spinner("Loading market data..."):
        prices = data_fetcher.get_prices(tickers, ctx["years"])
        info = data_fetcher.get_company_info(held)
    ui.data_status_banner()
    if prices.empty or BM not in prices.columns:
        st.error(f"Market data for {BM} is unavailable right now (Yahoo Finance may be rate-limiting). Try again in a few minutes.")
        st.stop()
    fresh, stale = data_fetcher.resolve_prices(prices, held)       # also saves today's prices as 'last known'
    for t, (px_, asof) in stale.items():
        ui.flag("warn", ui.md(f"Using last known price for {t} from {asof} — live data unavailable."))
    miss = [t for t in held if t not in prices.columns and t not in stale]
    if miss:
        st.warning(ui.md(f"No price data and no stored price for: {', '.join(miss)}. These are valued at $0 and left out of risk metrics."))
    fb = {t: v[0] for t, v in stale.items()}
    a = risk_engine.analyze(holdings, cash, prices, info, ctx["rf"], BM, fallback_prices=fb)
    a_ex = (risk_engine.analyze(holdings, cash, prices, info, ctx["rf"], BM, exclude=BM, fallback_prices=fb)
            if BM in set(held) else None)
    m, bm = a["metrics"], a["bench_metrics"]
    pos = a["positions"]
    weights = pos.set_index("ticker")["weight"]
    ui.page_header(**HERO, stat=("Total portfolio value", f"${a['total']:,.2f}"))

    # --- extra analytics (all numbers come from risk_engine) ---
    contrib = risk_engine.risk_contributions(weights, a["rets"]) if m else None
    eff, eff_flags = risk_engine.effective_weights(pos)
    adv = data_fetcher.get_avg_volume(held)
    days = risk_engine.days_to_trade(pos, adv)
    liq = risk_engine.liquidity_flags(days)
    stress = {}
    wins = tags_config.STRESS_WINDOWS
    if wins:
        s0 = (min(pd.Timestamp(v[0]) for v in wins.values()) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        s1 = (max(pd.Timestamp(v[1]) for v in wins.values()) + pd.Timedelta(days=5)).strftime("%Y-%m-%d")
        sp = data_fetcher.get_prices_range(tickers, s0, s1)
        if not sp.empty:
            srets = sp.ffill(limit=5).pct_change(fill_method=None)
            stress = {k: risk_engine.stress_test(weights, srets, BM, s, e) for k, (s, e) in wins.items()}

    ui.kpi_cards([
        {"label": "Total value", "value": f"${a['total']:,.2f}", "sub": f"{len(holdings)} holdings"},
        {"label": "Cash", "value": f"${cash:,.2f}", "sub": f"{cash / a['total']:.1%} of portfolio" if a["total"] else ""},
        {"label": "Invested", "value": f"${a['total'] - cash:,.2f}", "sub": f"{1 - cash / a['total']:.1%} of portfolio" if a["total"] else ""},
        {"label": "Benchmark", "value": BM, "sub": f"{LB} lookback"}])
    if m:
        st.download_button("Download meeting summary", file_name=f"{P.replace(' ', '_')}_summary_{LB}.md", mime="text/markdown",
                           data=ui.meeting_summary_md(P, LB, BM, ctx["rf"], a, a_ex, contrib, stress, eff_flags, liq))

    st.subheader(f"Risk metrics vs. {BM}")
    if not m:
        st.warning("Not enough overlapping price history (need 30+ trading days) to compute risk metrics.")
    else:
        st.caption(f"Lookback: {LB} · {m['n_days']} trading days ({m['start']:%b %d, %Y} to {m['end']:%b %d, %Y}) · "
                   f"risk-free rate {ctx['rf']:.2%} (3-month T-bill)")
        ui.kpi_cards([
            {"label": f"Beta ({LB})", "value": f"{m['beta']:.2f}", "sub": f"{BM}: {bm['beta']:.2f}"},
            {"label": f"Volatility ({LB})", "value": f"{m['vol']:.2%}", "sub": f"{BM}: {bm['vol']:.2%}"},
            {"label": f"Sharpe ({LB})", "value": f"{m['sharpe']:.2f}", "sub": f"{BM}: {bm['sharpe']:.2f}"},
            {"label": f"Max drawdown ({LB})", "value": f"{m['max_dd']:.2%}", "sub": f"{m['dd_peak']:%b %Y} to {m['dd_trough']:%b %Y}"},
            {"label": f"Correlation to {BM}", "value": f"{m['corr']:.2f}", "sub": f"{LB} daily returns"}])
        ir = "n/a" if pd.isna(m["info_ratio"]) else f"{m['info_ratio']:.2f}"
        ui.kpi_cards([
            {"label": "Annualized return", "value": f"{m['ann_return']:.2%}", "sub": f"{BM}: {bm['ann_return']:.2%}"},
            {"label": "Tracking error", "value": f"{m['tracking_error']:.2%}", "sub": f"vs. {BM}, annualized"},
            {"label": "Information ratio", "value": ir, "sub": "excess return per unit of tracking error"},
            {"label": "1-day 95% VaR", "value": f"{m['var95']:.2%}", "sub": f"{BM}: {bm['var95']:.2%}"},
            {"label": "1-day 95% CVaR", "value": f"{m['cvar95']:.2%}", "sub": f"{BM}: {bm['cvar95']:.2%}"}])
        if a_ex and a_ex["metrics"]:
            x = a_ex["metrics"]
            ui.flag("info", f"Ex-benchmark view. Beta excluding the {BM} holding: {x['beta']:.2f} (vs. {m['beta']:.2f} headline). "
                            f"Correlation: {x['corr']:.2f} (vs. {m['corr']:.2f}). Volatility: {x['vol']:.2%} (vs. {m['vol']:.2%}). "
                            f"The headline figures are inflated because the portfolio owns its own benchmark.")
        left, right = st.columns([1, 2])
        with left:
            ui.html_table(pd.DataFrame({"Metric": ["Annualized return", "Annualized volatility", "Sharpe ratio", "Max drawdown",
                                                   "1-day 95% VaR", "1-day 95% CVaR"],
                                        "Portfolio": [f"{m['ann_return']:.2%}", f"{m['vol']:.2%}", f"{m['sharpe']:.2f}", f"{m['max_dd']:.2%}",
                                                      f"{m['var95']:.2%}", f"{m['cvar95']:.2%}"],
                                        BM: [f"{bm['ann_return']:.2%}", f"{bm['vol']:.2%}", f"{bm['sharpe']:.2f}", f"{bm['max_dd']:.2%}",
                                             f"{bm['var95']:.2%}", f"{bm['cvar95']:.2%}"]}), right=("Portfolio", BM))
        with right:
            st.plotly_chart(ui.perf_chart(a["port_ret"], a["bench_ret"], BM), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(ui.drawdown_chart(a["port_ret"], a["bench_ret"], BM), use_container_width=True, config={"displayModeBar": False})

        st.subheader("Top contributors to volatility")
        if contrib is not None and len(contrib):
            ui.html_table(pd.DataFrame({"Ticker": contrib["ticker"], "Weight": contrib["weight"].map("{:.2%}".format),
                                        "Contribution to volatility": contrib["contribution"].map("{:.2%}".format),
                                        "Share of total risk": contrib["pct"].map("{:.1%}".format)}),
                          right=("Weight", "Contribution to volatility", "Share of total risk"))
            st.caption("Euler risk allocation using the covariance of daily returns over the lookback. "
                       "Contributions are in annualized volatility points; shares sum to 100% across all holdings.")

    st.subheader("Stress tests")
    if not stress:
        st.info("Stress-test history could not be loaded right now. The rest of the dashboard is unaffected.")
    else:
        for k, v in stress.items():
            if v is None:
                continue
            ui.kpi_cards([{"label": k, "value": "n/a" if pd.isna(v["ret"]) else f"{v['ret']:+.2%}",
                           "sub": f"{BM}: {v['bench_ret']:+.2%} · based on {v['coverage']:.0%} of portfolio value with available history"}])
        st.caption("Hypothetical: today's weights applied to each window's historical daily returns. Holdings with no history in a "
                   "window are treated as flat, and cash earns 0%. Not a forecast.")

    ui.render_flags(a, eff_flags=eff_flags, liq_flags=liq)

    st.subheader("Sector weightings")
    sec = a["sectors"]
    cc = st.columns([3, 2])
    cc[0].plotly_chart(ui.sector_donut(sec), use_container_width=True, config={"displayModeBar": False})
    with cc[1]:
        tbl = pd.DataFrame({"Sector": list(sec.index), "Weight": [f"{v:.2%}" for v in sec.values]})
        tbl.loc[len(tbl)] = ["Total", f"{sec.sum():.2%}"]
        ui.html_table(tbl, right=("Weight",), total_last=True)
    st.caption("Sectors follow the fund spreadsheet (see tags_config.py); broad ETFs such as QQQ, SPY and IWM are split across "
               "their component sectors. Sectors you pick when adding a holding take priority.")

    st.subheader("Holdings")
    funds = set(tags_config.ETF_LOOKTHROUGH) | set(tags_config.ETF_TOP_HOLDINGS)
    hb, ht = st.columns([2, 3])
    hb.plotly_chart(ui.holdings_bar(pos), use_container_width=True, config={"displayModeBar": False})
    with ht:
        ui.html_table(pd.DataFrame({
            "Ticker": pos["ticker"], "Sector": pos["sector"],
            "Shares": pos["shares"].map("{:,.2f}".format),
            "Price": [("n/a" if pd.isna(v) else f"${v:,.2f}") + ("*" if t in stale else "") for t, v in zip(pos["ticker"], pos["price"])],
            "Value": pos["value"].map("${:,.2f}".format), "Weight": pos["weight"].map("{:.2%}".format),
            "Effective weight (incl. ETFs)": ["n/a (fund)" if t in funds else f"{eff.get(t, 0):.2%}" for t in pos["ticker"]],
            "Days to trade": [("n/a" if pd.isna(days.get(t)) else f"{days[t]:.1f}") for t in pos["ticker"]],
            "Gain/Loss": [("n/a" if pd.isna(c) or pd.isna(p) else f"{p / c - 1:+.2%}") for c, p in zip(pos["avg_cost"], pos["price"])]}),
            right=("Shares", "Price", "Value", "Weight", "Effective weight (incl. ETFs)", "Days to trade", "Gain/Loss"))
    st.caption(ui.md("Effective weight adds each stock's share of the ETFs you own (top-10 estimates in tags_config.py). "
                     "Days to trade = shares / (20% of 20-day average volume). * = last known price, live data unavailable."))

    st.caption(ui.md(f"Notes. Portfolio returns apply today's weights to historical daily returns (no past trades modeled); "
                     f"cash earns 0%. Metrics use adjusted close; benchmark is {BM}. Sharpe = (mean daily return x 252 minus the "
                     f"3-month T-bill rate) / annualized volatility. VaR/CVaR are 1-day historical. Revenue-by-region, theme tags "
                     f"and ETF holdings are maintained estimates. See METHODOLOGY.md."))
    for n in a["notes"]:
        st.caption(f"Note: {n}")
    ui.footer()
