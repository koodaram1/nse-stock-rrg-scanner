import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mobile_ui import inject_css, esc, nav_bar, pretty_sector

st.set_page_config(
    page_title="NSE Stock RRG — Sector Chart",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed",
)
inject_css()

scan = st.session_state.get("scan")

st.markdown('<div class="mobile-title">NSE SECTOR RRG CHART</div>', unsafe_allow_html=True)
nav_bar("chart")

if not scan:
    st.info("Run the scanner from Dashboard first.")
    st.stop()

st.markdown(
    f'<div class="mobile-date">Data date: {esc(scan.get("data_date", "-"))} • Benchmark: NIFTY 50</div>',
    unsafe_allow_html=True,
)

latest = scan["sector_df"].copy()
histories = scan.get("sector_histories", {}) or {}

QUAD_COLORS = {
    "LEADING": "#22c55e",
    "IMPROVING": "#3b82f6",
    "WEAKENING": "#f59e0b",
    "LAGGING": "#ef4444",
    "NO DATA": "#94a3b8",
}


def _finite(v):
    try:
        return math.isfinite(float(v))
    except Exception:
        return False


def _axis_bounds(values):
    vals = [float(v) for v in values if _finite(v)]
    if not vals:
        return 90.0, 110.0
    lo = min(vals + [100.0])
    hi = max(vals + [100.0])
    pad = max(2.5, (hi - lo) * 0.18)
    return lo - pad, hi + pad


# ------------------------------------------------------------
# ETF-MOBILE-STYLE SECTOR SELECTION
# ------------------------------------------------------------
# Same presentation principle used in the ETF mobile chart:
#   1) keep the most important ranked names first;
#   2) add only a small amount of rotation context;
#   3) every displayed point has a name;
#   4) no anonymous/unwanted dots.
#
# Stock scanner calculations/rankings are NOT changed.

if "Rank" in latest.columns:
    latest["_rank"] = pd.to_numeric(latest["Rank"], errors="coerce")
    latest = latest.sort_values(["_rank", "Sector"], na_position="last").copy()
elif "Strength_Score" in latest.columns:
    latest["_strength"] = pd.to_numeric(latest["Strength_Score"], errors="coerce")
    latest = latest.sort_values(["_strength", "Sector"], ascending=[False, True]).copy()

latest["Quadrant"] = latest["Quadrant"].astype(str).str.upper()

wanted = []

# Always keep today's Top 5 ranked sectors.
for nm in latest["Sector"].dropna().astype(str).head(5):
    if nm not in wanted:
        wanted.append(nm)

# Add one useful context sector from Improving, Weakening and Lagging.
# This gives a maximum of 8 named sectors on mobile.
for quadrant_name in ["IMPROVING", "WEAKENING", "LAGGING"]:
    part = latest[latest["Quadrant"].eq(quadrant_name)].copy()

    # Prefer strongest momentum inside the quadrant, as in the ETF mobile chart.
    if "RS_Momentum" in part.columns:
        part["_mom"] = pd.to_numeric(part["RS_Momentum"], errors="coerce")
        part = part.sort_values("_mom", ascending=False)

    for nm in part["Sector"].dropna().astype(str):
        if nm not in wanted:
            wanted.append(nm)
            break

# If one quadrant has no valid candidate, fill remaining slots with next-ranked sectors.
for nm in latest["Sector"].dropna().astype(str):
    if len(wanted) >= 8:
        break
    if nm not in wanted:
        wanted.append(nm)

wanted = wanted[:8]

show = latest[latest["Sector"].astype(str).isin(wanted)].copy()

# Keep display order identical to the wanted priority.
_order = {name: i for i, name in enumerate(wanted)}
show["_display_order"] = show["Sector"].astype(str).map(_order)
show = show.sort_values("_display_order").copy()

# ------------------------------------------------------------
# AXIS RANGE — SELECTED SECTORS + THEIR 3-DAY TRAILS ONLY
# ------------------------------------------------------------
all_x = pd.to_numeric(show["RS_Ratio"], errors="coerce").dropna().tolist()
all_y = pd.to_numeric(show["RS_Momentum"], errors="coerce").dropna().tolist()

for key in show["Sector"].astype(str):
    hist = histories.get(key)
    if isinstance(hist, pd.DataFrame) and not hist.empty:
        tail = hist.tail(3)
        all_x += pd.to_numeric(tail.get("RS_Ratio"), errors="coerce").dropna().tolist()
        all_y += pd.to_numeric(tail.get("RS_Momentum"), errors="coerce").dropna().tolist()

xmin, xmax = _axis_bounds(all_x)
ymin, ymax = _axis_bounds(all_y)

fig = go.Figure()

# ------------------------------------------------------------
# FOUR COLORED QUADRANTS — SAME ETF MOBILE STYLE
# ------------------------------------------------------------
fig.add_shape(
    type="rect", x0=100, x1=xmax, y0=100, y1=ymax,
    fillcolor="rgba(34,197,94,0.10)", line_width=0, layer="below"
)
fig.add_shape(
    type="rect", x0=xmin, x1=100, y0=100, y1=ymax,
    fillcolor="rgba(59,130,246,0.10)", line_width=0, layer="below"
)
fig.add_shape(
    type="rect", x0=100, x1=xmax, y0=ymin, y1=100,
    fillcolor="rgba(245,158,11,0.10)", line_width=0, layer="below"
)
fig.add_shape(
    type="rect", x0=xmin, x1=100, y0=ymin, y1=100,
    fillcolor="rgba(239,68,68,0.10)", line_width=0, layer="below"
)

fig.add_vline(x=100, line_width=1, line_dash="dot", line_color="#8B949E")
fig.add_hline(y=100, line_width=1, line_dash="dot", line_color="#8B949E")

# Alternate label positions exactly to prevent the previous overlaps.
text_positions = [
    "top center",      # #1
    "bottom center",   # #2
    "middle left",     # #3
    "bottom left",     # #4
    "top left",        # #5
    "middle right",    # context
    "bottom right",    # context
    "top right",       # context
]

# ------------------------------------------------------------
# EVERY DISPLAYED SECTOR = NAMED CURRENT POINT + 3-DAY TRAIL
# No anonymous dots.
# ------------------------------------------------------------
for idx, (_, row) in enumerate(show.iterrows()):
    raw_name = str(row["Sector"])
    display_name = pretty_sector(raw_name)
    quad = str(row.get("Quadrant", "NO DATA")).upper()
    color = QUAD_COLORS.get(quad, QUAD_COLORS["NO DATA"])
    hist = histories.get(raw_name)

    if isinstance(hist, pd.DataFrame) and not hist.empty:
        tail = hist.tail(3).copy()
        hx = pd.to_numeric(tail.get("RS_Ratio"), errors="coerce")
        hy = pd.to_numeric(tail.get("RS_Momentum"), errors="coerce")
        mask = hx.notna() & hy.notna()
        hx, hy = hx[mask], hy[mask]

        if len(hx):
            fig.add_trace(
                go.Scatter(
                    x=hx,
                    y=hy,
                    mode="lines+markers",
                    line=dict(color=color, width=1.35),
                    marker=dict(size=3.5, color=color, opacity=0.68),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    is_top5 = idx < 5

    fig.add_trace(
        go.Scatter(
            x=[row["RS_Ratio"]],
            y=[row["RS_Momentum"]],
            mode="markers+text",
            text=[display_name],
            textposition=text_positions[idx % len(text_positions)],
            textfont=dict(
                size=(9 if len(display_name) > 20 else (10 if is_top5 else 9)),
                color=color,
            ),
            marker=dict(
                size=11 if is_top5 else 9,
                color=color,
                line=dict(width=1.2, color="#E5E7EB"),
            ),
            customdata=[[quad]],
            hovertemplate=(
                f"<b>{display_name}</b><br>"
                "RS Ratio: %{x:.2f}<br>"
                "RS Momentum: %{y:.2f}<br>"
                "Quadrant: %{customdata[0]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

# Quadrant labels.
fig.add_annotation(
    x=xmax, y=ymax, text="LEADING", showarrow=False,
    xanchor="right", yanchor="top",
    font=dict(color=QUAD_COLORS["LEADING"], size=11),
)
fig.add_annotation(
    x=xmin, y=ymax, text="IMPROVING", showarrow=False,
    xanchor="left", yanchor="top",
    font=dict(color=QUAD_COLORS["IMPROVING"], size=11),
)
fig.add_annotation(
    x=xmax, y=ymin, text="WEAKENING", showarrow=False,
    xanchor="right", yanchor="bottom",
    font=dict(color=QUAD_COLORS["WEAKENING"], size=11),
)
fig.add_annotation(
    x=xmin, y=ymin, text="LAGGING", showarrow=False,
    xanchor="left", yanchor="bottom",
    font=dict(color=QUAD_COLORS["LAGGING"], size=11),
)

fig.update_layout(
    height=485,
    margin=dict(l=18, r=18, t=15, b=30),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E5E7EB", size=11),
    xaxis=dict(
        title="RS Ratio",
        range=[xmin, xmax],
        gridcolor="rgba(148,163,184,0.12)",
        zeroline=False,
    ),
    yaxis=dict(
        title="RS Momentum",
        range=[ymin, ymax],
        gridcolor="rgba(148,163,184,0.12)",
        zeroline=False,
    ),
    hovermode="closest",
    showlegend=False,
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displaylogo": False, "responsive": True},
)

# Compact Top-5 summary beneath the chart.
# Avoid st.metric here because its large numeric font is too heavy for mobile.
st.markdown(
    """
    <style>
    .rrg-mini-head {
        font-size: 0.90rem;
        font-weight: 800;
        margin: 0.35rem 0 0.35rem 0;
    }
    .rrg-mini-row {
        display: grid;
        grid-template-columns: minmax(0, 1.75fr) 0.82fr 0.62fr 0.62fr;
        gap: 0.35rem;
        align-items: center;
        padding: 0.38rem 0;
        border-bottom: 1px solid rgba(148,163,184,0.15);
        font-size: 0.76rem;
        line-height: 1.20;
    }
    .rrg-mini-name {
        font-weight: 800;
        overflow-wrap: anywhere;
    }
    .rrg-mini-q {
        font-weight: 700;
        font-size: 0.72rem;
    }
    .rrg-mini-num {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .rrg-mini-label {
        color: #94a3b8;
        font-size: 0.63rem;
        display: block;
        margin-bottom: 0.05rem;
    }
    </style>
    <div class="rrg-mini-head">TOP 5 SECTORS</div>
    """,
    unsafe_allow_html=True,
)

top5 = show.head(5)
for i, (_, row) in enumerate(top5.iterrows(), start=1):
    sector = pretty_sector(str(row["Sector"]))
    quad = str(row.get("Quadrant", "-")).upper()
    rsr = pd.to_numeric(pd.Series([row.get("RS_Ratio")]), errors="coerce").iloc[0]
    rsm = pd.to_numeric(pd.Series([row.get("RS_Momentum")]), errors="coerce").iloc[0]
    rsr_txt = f"{float(rsr):.2f}" if _finite(rsr) else "-"
    rsm_txt = f"{float(rsm):.2f}" if _finite(rsm) else "-"
    q_color = QUAD_COLORS.get(quad, QUAD_COLORS["NO DATA"])

    st.markdown(
        f"""
        <div class="rrg-mini-row">
            <div class="rrg-mini-name">#{i} {esc(sector)}</div>
            <div class="rrg-mini-q" style="color:{q_color};">{esc(quad)}</div>
            <div class="rrg-mini-num"><span class="rrg-mini-label">RS Ratio</span>{rsr_txt}</div>
            <div class="rrg-mini-num"><span class="rrg-mini-label">RS Mom</span>{rsm_txt}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
