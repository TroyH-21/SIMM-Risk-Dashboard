"""Shared Streamlit UI: branding/CSS, sidebar, KPI cards, tables, charts, risk-flag panels."""
import html as _html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_fetcher
import risk_engine
import tags_config

AUTO = "Auto-detect (spreadsheet, then Yahoo)"
KEEP = "Keep current sector"
FONT = "Inter, Segoe UI, Helvetica, Arial, sans-serif"
INK = "#2A1A10"


# ------------------------------ text helpers ----------------------------------
def md(text):
    """Escape $ so Streamlit doesn't treat dollar amounts as LaTeX."""
    return str(text).replace("$", r"\$")


def esc(v):
    return _html.escape(str(v)).replace("$", "&#36;")


def sector_options(first=AUTO):
    return [first] + list(tags_config.SECTOR_CHOICES)


def sector_value(choice):
    return None if choice in (AUTO, KEEP) else choice


def parse_number(text, label, allow_blank=False):
    """Return (value, error). Plain-English errors for blank/non-numeric/negative input."""
    t = (text or "").replace(",", "").replace("$", "").strip()
    if t == "":
        return (None, None) if allow_blank else (None, f"Please enter {label}.")
    try:
        v = float(t)
    except ValueError:
        return None, f"{label} must be a number (you entered '{text}')."
    if not np.isfinite(v) or v < 0:
        return None, f"{label} can't be negative."
    return v, None


def fmt(kind, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return {"num": f"{v:.2f}", "pct": f"{v:.2%}", "usd": f"${v:,.2f}"}[kind]


def fmt_change(kind, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return {"num": f"{v:+.2f}", "pct": f"{v * 100:+.2f} pp", "usd": f"{'+' if v >= 0 else '-'}${abs(v):,.2f}"}[kind]


# ------------------------------ branding / CSS --------------------------------
def apply_branding():
    """Inject brand CSS + sidebar brand block. Call once at the top of every page."""
    B, Y, C, BD = config.BROWN, config.YELLOW, config.CREAM, config.BORDER
    st.session_state["_data_snapshot"], st.session_state["_data_error"] = None, ""   # reset the data-status flags each run
    st.markdown(f"""<style>
    #MainMenu, footer, .stDeployButton {{visibility:hidden;}}
    header[data-testid="stHeader"] {{background:transparent;}}
    .block-container {{padding-top:1.2rem; max-width:1280px;}}
    html, body, [class*="css"] {{font-family:{FONT};}}
    h2, h3 {{color:{B}; font-family:Georgia,'Times New Roman',serif; font-weight:700; letter-spacing:-0.01em;}}
    h2 {{margin-top:2rem; padding-bottom:.35rem; border-bottom:1px solid {BD}; position:relative;}}
    h2::after {{content:""; position:absolute; left:0; bottom:-1px; width:64px; height:3px; background:{Y};}}
    [data-testid="stVerticalBlockBorderWrapper"] {{border-radius:12px; border-color:{BD}; background:#fff;
        box-shadow:0 2px 8px rgba(75,38,21,.05);}}
    section[data-testid="stSidebar"] {{background:{C}; border-right:1px solid {BD};}}
    .stTabs [data-baseweb="tab"] {{font-weight:600; color:#8A6A52;}}
    .stTabs [aria-selected="true"] {{color:{B};}}
    .stTabs [data-baseweb="tab-highlight"] {{background-color:{Y}; height:3px;}}
    .stButton>button[kind="primary"], .stFormSubmitButton>button {{background:{B}; color:#fff; border:0; border-radius:8px; font-weight:600;}}
    .stButton>button[kind="primary"]:hover, .stFormSubmitButton>button:hover {{background:{config.BROWN_MID}; color:#fff;}}
    .hero {{display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap;
        background:linear-gradient(115deg,{B} 0%,#6A3A1F 100%); color:#fff; padding:28px 34px 24px; border-radius:14px;
        margin-bottom:1.2rem; border-bottom:5px solid {Y}; box-shadow:0 6px 18px rgba(75,38,21,.28);}}
    .hero .eyebrow {{color:{Y}; font-size:.72rem; letter-spacing:.2em; text-transform:uppercase; font-weight:700;}}
    .hero h1 {{color:#fff; margin:.25rem 0 .15rem; font-family:Georgia,serif; font-size:2.2rem; padding:0; font-weight:700; line-height:1.1;}}
    .hero .sub {{color:#E9DCCB; font-size:.92rem;}}
    .hero .stat {{text-align:right; border-left:1px solid rgba(245,184,0,.5); padding-left:24px;}}
    .hero .stat .hl {{color:{Y}; font-size:.68rem; letter-spacing:.16em; text-transform:uppercase; font-weight:700;}}
    .hero .stat .hv {{font-family:Georgia,serif; font-size:2rem; font-weight:700; color:#fff;}}
    .chip {{display:inline-block; background:rgba(255,255,255,.1); border:1px solid rgba(245,184,0,.55); color:#fff;
        border-radius:999px; padding:3px 12px; margin:12px 8px 0 0; font-size:.76rem; letter-spacing:.02em;}}
    .brand-side {{padding:.2rem 0 .9rem; border-bottom:2px solid {Y}; margin-bottom:.9rem;}}
    .brand-side .sch {{color:{Y}; background:{B}; display:inline-block; padding:2px 8px; border-radius:4px;
        font-size:.62rem; letter-spacing:.14em; text-transform:uppercase; font-weight:700;}}
    .brand-side b {{display:block; color:{B}; font-family:Georgia,serif; font-size:1.1rem; margin-top:6px; line-height:1.2;}}
    .brand-side span.t {{display:block; color:#8A6A52; font-size:.74rem; margin-top:2px;}}
    .kpi-row {{display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:6px 0 14px;}}
    .kpi {{background:#fff; border:1px solid {BD}; border-top:4px solid {B}; border-radius:10px; padding:14px 16px 12px;
        box-shadow:0 2px 8px rgba(75,38,21,.07);}}
    .kpi .kl {{color:#8A6A52; font-size:.66rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700;}}
    .kpi .kv {{color:{B}; font-family:Georgia,serif; font-size:1.7rem; font-weight:700; margin:2px 0; line-height:1.15;}}
    .kpi .ks {{color:#7C6A5A; font-size:.76rem; border-top:1px solid #F0E8DA; padding-top:5px; margin-top:4px;}}
    .flag {{display:flex; gap:12px; align-items:flex-start; padding:11px 14px; border-radius:8px; margin:8px 0;
        font-size:.92rem; border:1px solid; border-left:5px solid;}}
    .flag .badge {{flex:none; font-size:.62rem; letter-spacing:.12em; font-weight:800; padding:3px 8px; border-radius:4px; margin-top:2px;}}
    .flag.danger {{background:#FBEFEC; color:#6E1A10; border-color:#EBC9C2; border-left-color:#B03A2E;}}
    .flag.danger .badge {{background:#B03A2E; color:#fff;}}
    .flag.warn {{background:#FFF8E1; color:#5F4500; border-color:#F0DFA6; border-left-color:{Y};}}
    .flag.warn .badge {{background:{Y}; color:{B};}}
    .flag.ok {{background:#F1F6EE; color:#2F5D2A; border-color:#D4E4CD; border-left-color:#5E9B54;}}
    .flag.ok .badge {{background:#5E9B54; color:#fff;}}
    .flag.info {{background:#F4F1EC; color:#4A3B30; border-color:#E2D9CB; border-left-color:#9C8A76;}}
    .flag.info .badge {{background:#9C8A76; color:#fff;}}
    .tbl-wrap {{overflow-x:auto; border:1px solid {BD}; border-radius:10px;}}
    table.fund-table {{border-collapse:collapse; width:100%; font-size:.88rem;}}
    .fund-table th {{background:{B}; color:#fff; text-align:left; padding:10px 12px; font-weight:600; font-size:.72rem;
        letter-spacing:.07em; text-transform:uppercase; white-space:nowrap;}}
    .fund-table td {{padding:8px 12px; border-bottom:1px solid #F0E8DA; color:{INK};}}
    .fund-table tr:nth-child(even) td {{background:#FBF8F3;}}
    .fund-table tr.total td {{font-weight:700; background:#F3E9D2; border-top:2px solid {Y};}}
    .fund-table .r {{text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums;}}
    .foot {{margin-top:2.2rem; padding-top:.8rem; border-top:1px solid {BD}; color:#8A7A6A; font-size:.74rem; text-align:center;}}
    </style>""", unsafe_allow_html=True)
    st.sidebar.markdown(f'<div class="brand-side"><span class="sch">{esc(config.BRAND_SCHOOL)}</span>'
                        f'<b>{esc(config.BRAND_NAME)}</b><span class="t">{esc(config.BRAND_TAGLINE)}</span></div>',
                        unsafe_allow_html=True)


def page_header(title, subtitle="", eyebrow=None, chips=(), stat=None, slot=None):
    """Hero banner. stat=(label, value) shows a headline number on the right. slot=st.empty() lets a page
    draw the hero first and fill in the number once data has loaded."""
    chip_html = "".join(f'<span class="chip">{esc(c)}</span>' for c in chips)
    stat_html = (f'<div class="stat"><div class="hl">{esc(stat[0])}</div><div class="hv">{esc(stat[1])}</div></div>'
                 if stat else "")
    (slot or st).markdown(
        f'<div class="hero"><div><div class="eyebrow">{esc(eyebrow or config.BRAND_SCHOOL)}</div>'
        f'<h1>{esc(title)}</h1><div class="sub">{esc(subtitle)}</div>{chip_html}</div>{stat_html}</div>',
        unsafe_allow_html=True)


def footer():
    st.markdown(f'<div class="foot">{esc(config.BRAND_NAME)} · {esc(config.BRAND_SCHOOL)} · For internal fund use only; '
                f'not investment advice. Market data from Yahoo Finance and may be delayed.</div>', unsafe_allow_html=True)


def kpi_cards(items):
    """items: list of dicts with label, value, sub (optional)."""
    cards = "".join(f'<div class="kpi"><div class="kl">{esc(i["label"])}</div><div class="kv">{esc(i["value"])}</div>'
                    + (f'<div class="ks">{esc(i["sub"])}</div>' if i.get("sub") else "") + "</div>" for i in items)
    st.markdown(f'<div class="kpi-row">{cards}</div>', unsafe_allow_html=True)


FLAG_LABEL = {"danger": "ALERT", "warn": "WATCH", "ok": "CLEAR", "info": "NOTE"}


def data_status_banner():
    """Tell the user when saved market data (not live Yahoo data) is being shown, and why live data failed."""
    ss = st.session_state
    if ss.get("_data_snapshot"):
        flag("info", f"Live prices are unavailable right now, so some or all of this page uses saved market data through "
                     f"{ss['_data_snapshot']}. Metrics reflect that date, not today.")
    if ss.get("_data_error"):
        st.caption(f"Technical detail: {ss['_data_error']}")


def flag(kind, text):
    st.markdown(f'<div class="flag {kind}"><span class="badge">{FLAG_LABEL[kind]}</span><span>{esc(text)}</span></div>',
                unsafe_allow_html=True)


def html_table(df, right=(), total_last=False):
    """Branded table. `right` = column names to right-align; total_last styles the last row."""
    head = "".join(f'<th class="{"r" if c in right else ""}">{esc(c)}</th>' for c in df.columns)
    body, n = "", len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        cls = ' class="total"' if total_last and i == n - 1 else ""
        body += f"<tr{cls}>" + "".join(f'<td class="{"r" if c in right else ""}">{esc(row[c])}</td>' for c in df.columns) + "</tr>"
    st.markdown(f'<div class="tbl-wrap"><table class="fund-table"><thead><tr>{head}</tr></thead>'
                f'<tbody>{body}</tbody></table></div>', unsafe_allow_html=True)


# ------------------------------ sidebar ---------------------------------------
def sidebar_controls():
    """Sidebar shared by both pages; choices persist across pages via session_state."""
    ss = st.session_state
    portfolio = st.sidebar.selectbox("Portfolio", config.PORTFOLIOS,
                                     index=config.PORTFOLIOS.index(ss.get("portfolio", config.PORTFOLIOS[0])))
    opts = list(config.LOOKBACK_OPTIONS)
    lookback = st.sidebar.radio("Lookback", opts, horizontal=True,
                                index=opts.index(ss.get("lookback", config.DEFAULT_LOOKBACK)))
    rf_default, rf_src = data_fetcher.get_risk_free_rate()
    rf_pct = st.sidebar.number_input("Risk-free rate: 3-month T-bill (%)", 0.0, 20.0,
                                     float(ss.get("rf_pct", round(rf_default * 100, 2))),
                                     step=0.05, format="%.2f", help=f"Default: {rf_src}. You can override it.")
    ss.update(portfolio=portfolio, lookback=lookback, rf_pct=rf_pct)
    bench = config.benchmark_for(portfolio)
    st.sidebar.caption(f"Benchmark for this portfolio: **{bench}**")
    return {"portfolio": portfolio, "lookback": lookback, "years": config.LOOKBACK_OPTIONS[lookback],
            "rf": rf_pct / 100, "benchmark": bench}


# ------------------------------ charts ----------------------------------------
def style_fig(fig, height=None):
    fig.update_layout(font=dict(family=FONT, color=INK, size=12), colorway=config.COLORWAY,
                      plot_bgcolor="white", paper_bgcolor="white", legend=dict(orientation="h", y=1.1, x=0),
                      margin=dict(t=40, b=30, l=44, r=20), hoverlabel=dict(bgcolor="white", font_size=12),
                      **({"height": height} if height else {}))
    fig.update_xaxes(showgrid=False, linecolor="#D9CDBB", ticks="outside", tickcolor="#D9CDBB")
    fig.update_yaxes(gridcolor="#F0E8DA", zeroline=False)
    return fig


def perf_chart(port, bench, bench_name):
    """Growth of 100: portfolio vs benchmark."""
    p = risk_engine.cumulative_index(port)
    b = risk_engine.cumulative_index(bench.loc[port.index])
    fig = go.Figure([
        go.Scatter(x=p.index, y=p, name="Portfolio", line=dict(color=config.BROWN, width=2.6),
                   fill="tozeroy", fillcolor="rgba(75,38,21,0.06)", hovertemplate="%{y:.1f}"),
        go.Scatter(x=b.index, y=b, name=bench_name, line=dict(color=config.YELLOW, width=2.4), hovertemplate="%{y:.1f}")])
    fig.update_layout(hovermode="x unified", title=dict(text="Growth of 100", font=dict(size=14, color=config.BROWN)))
    fig.update_yaxes(range=[min(p.min(), b.min()) * 0.92, max(p.max(), b.max()) * 1.04])
    return style_fig(fig, 340)


def drawdown_chart(port, bench, bench_name):
    d1 = risk_engine.drawdown_series(port)
    d2 = risk_engine.drawdown_series(bench.loc[port.index])
    fig = go.Figure([
        go.Scatter(x=d1.index, y=d1, name="Portfolio", line=dict(color="#9B3B22", width=1.8), fill="tozeroy",
                   fillcolor="rgba(155,59,34,0.18)", hovertemplate="%{y:.2%}"),
        go.Scatter(x=d2.index, y=d2, name=bench_name, line=dict(color=config.YELLOW, width=1.6), hovertemplate="%{y:.2%}")])
    fig.update_layout(hovermode="x unified", yaxis_tickformat=".0%",
                      title=dict(text="Drawdown from peak", font=dict(size=14, color=config.BROWN)))
    return style_fig(fig, 260)


def sector_donut(sectors, height=380):
    """Donut of sector weights (Series of fractions). Cash is always grey."""
    colors, i = [], 0
    for n in sectors.index:
        if n == "Cash":
            colors.append("#BDB4A6")
        else:
            colors.append(config.SECTOR_COLORS[i % len(config.SECTOR_COLORS)]); i += 1
    fig = go.Figure(go.Pie(labels=list(sectors.index), values=list(sectors.values), hole=0.62, sort=False,
                           marker=dict(colors=colors, line=dict(color="#fff", width=2)), textinfo="percent",
                           textposition="outside", hovertemplate="%{label}: %{percent}<extra></extra>"))
    fig.add_annotation(text="<b>Sector</b><br>Mix", showarrow=False, font=dict(size=15, color=config.BROWN, family="Georgia"))
    fig.update_layout(height=height, margin=dict(t=20, b=20, l=10, r=10), showlegend=True,
                      legend=dict(orientation="v", y=0.5), paper_bgcolor="white", font=dict(family=FONT, color=INK))
    return fig


def holdings_bar(positions, n=10):
    top = positions.head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=top["weight"], y=top["ticker"], orientation="h", marker_color=config.BROWN,
                           text=[f"{w:.1%}" for w in top["weight"]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.2%}<extra></extra>"))
    fig.update_layout(xaxis_tickformat=".0%", title=dict(text=f"Top {len(top)} positions by weight",
                                                         font=dict(size=14, color=config.BROWN)))
    style_fig(fig, 40 * len(top) + 90)
    fig.update_yaxes(gridcolor="white")
    return fig


def corr_heatmap(df):
    """Rows = pitched tickers, columns = top existing holdings."""
    fig = go.Figure(go.Heatmap(z=df.values, x=list(df.columns), y=list(df.index), zmin=0, zmax=1,
                               colorscale=[[0, "#F7F2EA"], [0.55, "#F5B800"], [1, "#4B2615"]],
                               text=[[("n/a" if pd.isna(v) else f"{v:.2f}") for v in row] for row in df.values],
                               texttemplate="%{text}", xgap=3, ygap=3, colorbar=dict(title="Corr.", thickness=12),
                               hovertemplate="%{y} vs %{x}: %{text}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", gridcolor="white")
    fig.update_xaxes(side="top")
    return style_fig(fig, 110 + 46 * len(df))


def rate_meter(rate):
    """Horizontal five-zone sensitivity meter with a marker at the portfolio's score (4 decimals)."""
    s = float(max(-1.0, min(1.0, rate["score"])))
    zones = [(-1, -.5, "Low", "#D8E4D0"), (-.5, -.2, "Mod. Low", "#E9E6C6"), (-.2, .2, "Moderate", "#F3DB8C"),
             (.2, .5, "Mod. High", "#E0A93B"), (.5, 1, "High", "#8C4A22")]
    fig = go.Figure()
    for x0, x1, lab, col in zones:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0, y1=1, fillcolor=col, line=dict(color="white", width=3))
        fig.add_annotation(x=(x0 + x1) / 2, y=0.5, text=lab, showarrow=False,
                           font=dict(size=11, color="#fff" if col == "#8C4A22" else INK))
    fig.add_shape(type="line", x0=s, x1=s, y0=-0.12, y1=1.12, line=dict(color=config.BROWN, width=3))
    fig.add_trace(go.Scatter(x=[s], y=[1.28], mode="markers", hoverinfo="skip",
                             marker=dict(symbol="triangle-down", size=15, color=config.BROWN)))
    fig.add_annotation(x=s, y=1.9, text=f"<b>{rate['score']:+.4f}</b>", showarrow=False,
                       font=dict(size=24, color=config.BROWN, family="Georgia"))
    fig.update_xaxes(range=[-1.04, 1.04], tickvals=[-1, -.5, 0, .5, 1], ticktext=["-1.0", "-0.5", "0", "+0.5", "+1.0"],
                     showgrid=False, zeroline=False, linecolor="#D9CDBB")
    fig.update_yaxes(range=[-0.35, 2.35], visible=False)
    fig.update_layout(height=210, showlegend=False, margin=dict(t=10, b=30, l=20, r=20), plot_bgcolor="white",
                      paper_bgcolor="white", font=dict(family=FONT, color=INK))
    return fig


# ------------------------------ risk flags ------------------------------------
def render_flags(a, pitch=False, eff_flags=None, liq_flags=None):
    """Hidden-risk flags. pitch=True words the concentration banner for a pitch.
    eff_flags: single-name flags from ETF look-through; liq_flags: slow-to-trade positions."""
    st.subheader("Risk Flags")
    conc = a["concentration"]
    if conc:
        parts = [f"{c['name']} to {c['weight']:.1%} (limit {c['limit']:.0%})" if pitch else
                 f"{c['name']} is {c['weight']:.1%} (limit {c['limit']:.0%})" for c in conc]
        flag("danger", ("This pitch pushes " if pitch else "Concentration limit exceeded: ") + " and ".join(parts) + ".")
    else:
        flag("ok", "No single stock above 8% and no sector above 30%.")
    flagged = False
    for th, d in a["themes"].items():
        if d["weight"] > config.LIMIT_THEME:
            flagged = True
            flag("warn", f"{d['weight']:.0%} of the portfolio is exposed to the {th} theme "
                         f"({', '.join(d['tickers'])}). These names tend to fall together.")
    etfs = set(tags_config.ETF_LOOKTHROUGH)
    overlap = [(x, y, c) for x, y, c in a["clusters"] if x in etfs and y in etfs]
    for x, y, c in [p for p in a["clusters"] if p not in overlap]:
        flagged = True
        flag("warn", f"{x} and {y} have a return correlation of {c:.2f} (above {config.CORR_CLUSTER}). "
                     "They behave like one position.")
    for x, y, c in overlap:
        flag("info", f"Expected overlap (broad ETFs): {x} and {y} have a return correlation of {c:.2f}. "
                     "This is normal for index funds and is not counted as a hidden cluster.")
    for e in eff_flags or []:
        flagged = True
        flag("warn", f"{e['name']} effective weight is {e['effective']:.2%} including ETF holdings "
                     f"(direct {e['direct']:.2%}): {e['reason']}.")
    for t, dys in liq_flags or []:
        flagged = True
        flag("warn", f"{t} would take about {dys:.1f} trading days to sell at {config.LIQUIDITY_PARTICIPATION:.0%} of average daily "
                     f"volume (limit {config.LIQUIDITY_DAYS_FLAG} days).")
    geo = a["geo"]
    for reg in ["China", "Taiwan"]:
        v = geo["regions"].get(reg)
        if v is not None and not np.isnan(v) and v > config.LIMIT_REGION:
            flagged = True
            flag("warn", f"About {v:.0%} of revenue (weighted by holdings) comes from {reg} (limit {config.LIMIT_REGION:.0%}).")
    if not flagged:
        flag("ok", "No theme, correlation-cluster or geographic flags.")
    c1, c2 = st.columns(2)
    with c1:
        r = a["rate"]
        st.markdown("**Interest-rate sensitivity**")
        st.plotly_chart(rate_meter(r), use_container_width=True, config={"displayModeBar": False})
        st.caption(md(f"Score {r['score']:+.4f} ({r['label']}). A rising-rate environment has historically "
                      f"pressured ~{r['pressured']:.0%} of this portfolio."))
    with c2:
        st.markdown("**Revenue by region (estimates)**")
        regs = geo["regions"]
        html_table(pd.DataFrame({"Region": list(regs), "Weighted revenue share": [fmt("pct", v) for v in regs.values()]}),
                   right=("Weighted revenue share",))
        st.caption(f"Based on {geo['coverage']:.0%} of portfolio value with available estimates "
                   f"(edit tags_config.py to add more). Not covered: {', '.join(geo['missing']) or 'none'}.")


# ------------------------------ meeting summary -------------------------------
def meeting_summary_md(P, LB, BM, rf, a, a_ex, contrib, stress, eff_flags, liq_flags):
    """One-page Markdown summary for fund meetings (open in any editor, paste into Docs, or print to PDF)."""
    m, bm = a["metrics"], a["bench_metrics"]
    L = [f"# {P} - Meeting Summary", f"{config.BRAND_NAME} | {config.BRAND_SCHOOL}",
         f"Lookback {LB} | Benchmark {BM} | Risk-free rate {rf:.2%} (3-month T-bill)", "",
         f"**Total value:** ${a['total']:,.2f} | **Cash:** ${a['cash']:,.2f} ({a['cash'] / a['total']:.1%})", ""]
    if m:
        L += ["## Headline metrics", "| Metric | Portfolio | " + BM + " |", "|---|---|---|",
              f"| Beta | {m['beta']:.2f} | {bm['beta']:.2f} |", f"| Annualized return | {m['ann_return']:.2%} | {bm['ann_return']:.2%} |",
              f"| Volatility | {m['vol']:.2%} | {bm['vol']:.2%} |", f"| Sharpe | {m['sharpe']:.2f} | {bm['sharpe']:.2f} |",
              f"| Max drawdown | {m['max_dd']:.2%} | {bm['max_dd']:.2%} |", f"| Correlation to {BM} | {m['corr']:.2f} | 1.00 |",
              f"| Tracking error | {m['tracking_error']:.2%} | - |",
              f"| Information ratio | {'n/a' if pd.isna(m['info_ratio']) else format(m['info_ratio'], '.2f')} | - |",
              f"| 1-day 95% VaR / CVaR | {m['var95']:.2%} / {m['cvar95']:.2%} | {bm['var95']:.2%} / {bm['cvar95']:.2%} |", ""]
        if a_ex and a_ex["metrics"]:
            x = a_ex["metrics"]
            L += [f"Ex-benchmark view (excluding the {BM} holding): beta {x['beta']:.2f} (headline {m['beta']:.2f}), "
                  f"correlation {x['corr']:.2f}, volatility {x['vol']:.2%}.", ""]
    L += ["## Risk flags"]
    flags = [f"- Concentration: {c['name']} at {c['weight']:.1%} (limit {c['limit']:.0%})" for c in a["concentration"]]
    flags += [f"- Theme: {th} at {d['weight']:.0%} ({', '.join(d['tickers'])})" for th, d in a["themes"].items()
              if d["weight"] > config.LIMIT_THEME]
    flags += [f"- Effective weight: {e['name']} {e['effective']:.2%} ({e['reason']})" for e in eff_flags]
    flags += [f"- Liquidity: {t} ~{d:.1f} days to trade" for t, d in liq_flags]
    flags += [f"- Rate sensitivity: {a['rate']['score']:+.4f} ({a['rate']['label']})"]
    L += flags + ["", "## Top 10 positions", "| Ticker | Sector | Value | Weight |", "|---|---|---|---|"]
    L += [f"| {r.ticker} | {r.sector} | ${r.value:,.2f} | {r.weight:.2%} |" for r in a["positions"].head(10).itertuples()]
    L += ["", "## Sector weights", "| Sector | Weight |", "|---|---|"] + [f"| {s} | {w:.2%} |" for s, w in a["sectors"].items()]
    if contrib is not None and len(contrib):
        L += ["", "## Top contributors to volatility", "| Ticker | Weight | Share of risk |", "|---|---|---|"]
        L += [f"| {r.ticker} | {r.weight:.2%} | {r.pct:.1%} |" for r in contrib.itertuples()]
    if stress:
        L += ["", "## Stress tests (today's weights on historical windows)", "| Window | Portfolio | " + BM + " | Coverage |", "|---|---|---|---|"]
        L += [f"| {k} | {v['ret']:.2%} | {v['bench_ret']:.2%} | {v['coverage']:.0%} |" for k, v in stress.items() if v]
    L += ["", "_Backtest using current weights, not realized performance. Reference data in tags_config.py are estimates. "
              "Not investment advice._"]
    return "\n".join(L)
