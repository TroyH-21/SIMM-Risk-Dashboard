"""Pitch Simulator: test one or several pitched trades together before the vote."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config, data_fetcher, db_manager, risk_engine, tags_config, ui_components as ui

st.set_page_config(page_title=f"{config.BRAND_NAME} | Pitch Simulator", layout="wide")
ui.apply_branding()
db_manager.seed_if_empty()
ctx = ui.sidebar_controls()
P, LB, BM = ctx["portfolio"], ctx["lookback"], ctx["benchmark"]
holdings, cash = db_manager.get_holdings(P), db_manager.get_cash(P)

ui.page_header("Pitch Simulator", f"{P} · test several pitches together before the vote", "Pitch Analysis",
               chips=[f"Cash available: ${cash:,.2f}", f"Benchmark: {BM}", f"Lookback: {LB}"],
               stat=("Portfolio cash", f"${cash:,.2f}"))

def _f(v, fmt_):
    return "n/a" if v is None or pd.isna(v) else format(v, fmt_)


def pitch_history():
    """Saved pitches for the selected portfolio, with their before/after metric snapshots."""
    st.subheader("Pitch history")
    ph = db_manager.get_pitches(P)
    if ph.empty:
        st.caption("No pitches saved for this portfolio yet.")
    else:
        ui.html_table(pd.DataFrame({
            "ID": ph["id"], "Date": ph["timestamp"].astype(str).str[:10], "Presenter": ph["presenter"], "Trades": ph["tickers"],
            "Thesis": ph["thesis"],
            "Beta": [f"{_f(b, '.2f')} to {_f(a_, '.2f')}" for b, a_ in zip(ph["beta_before"], ph["beta_after"])],
            "Volatility": [f"{_f(b, '.2%')} to {_f(a_, '.2%')}" for b, a_ in zip(ph["vol_before"], ph["vol_after"])],
            "Sharpe": [f"{_f(b, '.2f')} to {_f(a_, '.2f')}" for b, a_ in zip(ph["sharpe_before"], ph["sharpe_after"])],
            "Max drawdown": [f"{_f(b, '.2%')} to {_f(a_, '.2%')}" for b, a_ in zip(ph["mdd_before"], ph["mdd_after"])],
            "Outcome / notes": ph["outcome"].fillna("")}))
        with st.form("pitch_outcome"):
            c1, c2 = st.columns([1, 3])
            pid = c1.selectbox("Pitch ID", list(ph["id"]))
            out = c2.text_input("Outcome / notes (e.g. approved, bought at $X, up 8% since)")
            if st.form_submit_button("Update outcome"):
                db_manager.set_pitch_outcome(pid, out.strip()); st.rerun()


ss = st.session_state
if ss.pop("pitch_flash", None):
    ui.flag("ok", ss.get("pitch_flash_msg", "Done."))

st.subheader("Pitched trades")
st.caption("Add one row per stock pitched. Use the empty row at the bottom to add more (press the + icon or click the last row). "
           "Trades are applied top to bottom, so a sell placed above a buy can fund it.")
blank = pd.DataFrame({"Ticker": ["", "", ""], "Action": ["Buy"] * 3, "Unit": ["Dollars"] * 3,
                      "Amount": [np.nan] * 3, "Sector": [ui.AUTO] * 3})
# Keyed by portfolio (and a reset counter) so rows never carry over when you switch portfolios or record trades.
edited = st.data_editor(
    blank, num_rows="dynamic", hide_index=True, use_container_width=True,
    key=f"pitch_table_{P}_{ss.get('pitch_reset', 0)}",
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", help="Yahoo Finance symbol, e.g. NVDA"),
        "Action": st.column_config.SelectboxColumn("Action", options=["Buy", "Sell"], required=True),
        "Unit": st.column_config.SelectboxColumn("Amount in", options=["Dollars", "Shares"], required=True),
        "Amount": st.column_config.NumberColumn("Amount", min_value=0.0, format="%.2f"),
        "Sector": st.column_config.SelectboxColumn("Sector (new positions)", options=ui.sector_options(ui.AUTO), required=True)})
run = st.button("Run simulation", type="primary")

if run:                                             # validate the table, then remember the result across reruns
    trades, errs = [], []
    for i, r in edited.iterrows():
        t = "" if pd.isna(r["Ticker"]) else str(r["Ticker"]).upper().strip()
        amt = r["Amount"]
        if not t and pd.isna(amt):
            continue                                # empty row
        if not t:
            errs.append(f"Row {i + 1}: enter a ticker."); continue
        if pd.isna(amt) or amt <= 0:
            errs.append(f"Row {i + 1} ({t}): enter an amount greater than zero."); continue
        ok, price, name = data_fetcher.validate_ticker(t)
        if not ok:
            errs.append(f"Row {i + 1}: we couldn't find market data for '{t}'. Check the ticker symbol."); continue
        shares = amt / price if r["Unit"] == "Dollars" else amt
        trades.append({"ticker": t, "side": r["Action"], "shares": float(shares), "price": price,
                       "sector": ui.sector_value(r["Sector"]), "name": name})
    ss.pop("pitch_sim", None)
    if not trades and not errs:
        errs.append("Enter at least one trade.")
    _, _, trade_errs, log = risk_engine.apply_trades(holdings, cash, trades) if trades else (None, None, [], [])
    for e in errs + trade_errs:
        ui.flag("danger", e)
    if errs or trade_errs:
        st.error("Fix the items above and run the simulation again. Nothing was simulated.")
    else:
        ss["pitch_sim"] = {"portfolio": P, "trades": trades}

sim = ss.get("pitch_sim")
if not sim or sim["portfolio"] != P:
    if not run:
        st.info("Fill in the table above, then click **Run simulation**.")
    pitch_history()
    ui.footer(); st.stop()

new_h, new_cash, trade_errs, log = risk_engine.apply_trades(holdings, cash, sim["trades"])
if trade_errs:                                      # holdings changed since the simulation was run
    for e in trade_errs:
        ui.flag("danger", e)
    ss.pop("pitch_sim", None)
    st.error("Holdings or cash changed since this simulation. Please run it again.")
    ui.footer(); st.stop()

st.subheader("Trade summary")
ui.html_table(pd.DataFrame([{"Ticker": t["ticker"], "Name": t["name"], "Action": t["side"],
                             "Shares": f"{t['shares']:,.4f}", "Price": f"${t['price']:,.2f}",
                             "Value": f"${t['shares'] * t['price']:,.2f}",
                             "Position": "New position" if t["new"] else "Existing position"} for t in log]),
              right=("Shares", "Price", "Value"))
net = sum((t["shares"] * t["price"]) * (-1 if t["side"] == "Buy" else 1) for t in log)
st.caption(ui.md(f"Net cash {'used' if net < 0 else 'raised'}: ${abs(net):,.2f}. Cash after all trades: ${new_cash:,.2f}."))

# ---- compute before / after ----
pitched = list(dict.fromkeys(t["ticker"] for t in log))
held = list(holdings["ticker"])
all_t = held + pitched + [BM]
with st.spinner("Running simulation..."):
    prices = data_fetcher.get_prices(all_t, ctx["years"])
    info = data_fetcher.get_company_info(sorted(set(held) | set(pitched)))
gone = [t for t in pitched + [BM] if t not in prices.columns]
ui.data_status_banner()
if prices.empty or gone:
    st.error(f"Price history is unavailable right now for: {', '.join(gone) or 'all tickers'}. Try again shortly.")
    st.stop()
fresh, stale = data_fetcher.resolve_prices(prices, all_t)
for t, (px_, asof) in stale.items():
    ui.flag("warn", ui.md(f"Using last known price for {t} from {asof} — live data unavailable."))
fb = {t: v[0] for t, v in stale.items()}
a0 = risk_engine.analyze(holdings, cash, prices, info, ctx["rf"], BM, fallback_prices=fb)
a1 = risk_engine.analyze(new_h, new_cash, prices, info, ctx["rf"], BM, fallback_prices=fb)

st.subheader("Before vs. After")
rows = risk_engine.comparison_rows(a0, a1, pitched, BM)
by = {r["metric"]: r for r in rows}
ui.kpi_cards([{"label": k, "value": ui.fmt(by[k]["kind"], by[k]["after"]),
               "sub": f"Before {ui.fmt(by[k]['kind'], by[k]['before'])}  ·  Change {ui.fmt_change(by[k]['kind'], by[k]['change'])}"}
              for k in ["Beta", "Annualized Volatility", "Sharpe Ratio", "Maximum Drawdown", "Tracking Error"]])
ui.html_table(pd.DataFrame([{"Metric": r["metric"], "Before": ui.fmt(r["kind"], r["before"]),
                             "After": ui.fmt(r["kind"], r["after"]), "Change": ui.fmt_change(r["kind"], r["change"]),
                             "What it means": r["text"]} for r in rows]), right=("Before", "After", "Change"))
w_sum = a1["positions"]["weight"].sum() + (new_cash / a1["total"] if a1["total"] else 0)
st.caption(ui.md(f"Risk metrics use a {LB} lookback with today's weights applied historically, measured against {BM}. "
                 f"After-portfolio weights (positions + cash) sum to {w_sum:.2%}. Risk-free rate {ctx['rf']:.2%} (3-month T-bill)."))
for n in a1["notes"]:
    st.caption(f"Note: {n}")

st.subheader("Sector weights: before vs. after")
sec = pd.concat([a0["sectors"].rename("Before"), a1["sectors"].rename("After")], axis=1).fillna(0)
sec["Change"] = sec["After"] - sec["Before"]
fig = go.Figure([go.Bar(name="Before", x=sec.index, y=sec["Before"], marker_color="#C9B28F"),
                 go.Bar(name="After", x=sec.index, y=sec["After"], marker_color=config.BROWN)])
fig.update_layout(barmode="group", yaxis_tickformat=".0%")
cc = st.columns([3, 2])
cc[0].plotly_chart(ui.style_fig(fig, 400), use_container_width=True, config={"displayModeBar": False})
tbl = pd.DataFrame({"Sector": list(sec.index), "Before": sec["Before"].map("{:.2%}".format),
                    "After": sec["After"].map("{:.2%}".format), "Change": (sec["Change"] * 100).map("{:+.2f} pp".format)})
tbl.loc[len(tbl)] = ["Total", f"{sec['Before'].sum():.2%}", f"{sec['After'].sum():.2%}", "n/a"]
with cc[1]:
    ui.html_table(tbl, right=("Before", "After", "Change"), total_last=True)

_, eff_flags = risk_engine.effective_weights(a1["positions"])
ui.render_flags(a1, pitch=True, eff_flags=eff_flags)

st.subheader("Correlation with top holdings")
cm = risk_engine.pitch_corr_matrix(pitched, a0["positions"], a1["rets"])
if cm.empty or cm.shape[1] == 0:
    st.caption("No other holdings to compare against.")
else:
    st.plotly_chart(ui.corr_heatmap(cm), use_container_width=True, config={"displayModeBar": False})
    st.caption(f"Daily-return correlation over the {LB} lookback between each pitched stock (rows) and the five largest "
               f"current holdings (columns). Darker = moves more closely together; above {config.CORR_CLUSTER} is flagged as a cluster.")

# ---- audit trail: record trades / save pitch ----
def _num(m, k):
    return None if not m or pd.isna(m.get(k)) else float(m[k])


st.subheader("Record these trades")
st.caption("Recording updates the portfolio's holdings and cash and writes one line per trade to the trade history. "
           "Only do this once the fund has actually approved and placed the trades.")
with st.form("record_trades"):
    c1, c2 = st.columns(2)
    who = c1.text_input("Your name (required)")
    note = c2.text_input("Note (optional)")
    if st.form_submit_button("Record these trades"):
        if not who.strip():
            st.error("Please enter your name so the trade log shows who recorded it.")
        else:
            old = holdings.set_index("ticker")
            for _, r in new_h.iterrows():
                if r["ticker"] in old.index and abs(old.at[r["ticker"], "shares"] - r["shares"]) < 1e-9:
                    continue                                   # unchanged holding: no write needed
                db_manager.save_holding(P, r["ticker"], r["shares"], r["avg_cost"], r.get("sector"))
            for t in set(holdings["ticker"]) - set(new_h["ticker"]):
                db_manager.remove_holding(P, t)
            db_manager.save_cash(P, new_cash)
            for t in log:
                db_manager.log_trade(P, t["ticker"], t["side"], t["shares"], t["price"], who.strip(), note.strip())
            ss.pop("pitch_sim", None)
            ss["pitch_reset"] = ss.get("pitch_reset", 0) + 1
            ss["pitch_flash"] = True
            ss["pitch_flash_msg"] = f"Recorded {len(log)} trade(s) for {P}. Holdings and cash are updated; see Trade history on the dashboard."
            st.rerun()

st.subheader("Save this pitch")
st.caption("Saves the thesis and the before/after risk numbers so the fund can review the call later. Does not change holdings.")
with st.form("save_pitch"):
    c1, c2 = st.columns([1, 2])
    presenter = c1.text_input("Presenter (required)")
    thesis = c2.text_input("Thesis (required)")
    if st.form_submit_button("Save this pitch"):
        if not presenter.strip() or not thesis.strip():
            st.error("Please enter the presenter and a thesis.")
        else:
            m0, m1 = a0["metrics"], a1["metrics"]
            db_manager.log_pitch({"portfolio": P, "presenter": presenter.strip(), "thesis": thesis.strip(),
                                  "tickers": ", ".join(f"{t['side']} {t['ticker']}" for t in log),
                                  "beta_before": _num(m0, "beta"), "beta_after": _num(m1, "beta"),
                                  "vol_before": _num(m0, "vol"), "vol_after": _num(m1, "vol"),
                                  "sharpe_before": _num(m0, "sharpe"), "sharpe_after": _num(m1, "sharpe"),
                                  "mdd_before": _num(m0, "max_dd"), "mdd_after": _num(m1, "max_dd"), "outcome": ""})
            st.success("Pitch saved. It now appears in Pitch history below.")
pitch_history()
ui.footer()
