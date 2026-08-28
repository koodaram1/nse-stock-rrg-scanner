import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from mobile_ui import inject_css,esc,nav_bar,pretty_sector

st.set_page_config(page_title="NSE Stock RRG — Sector Chart",page_icon="📊",layout="centered",initial_sidebar_state="collapsed")
inject_css(); scan=st.session_state.get("scan")
st.markdown('<div class="mobile-title">NSE SECTOR RRG CHART</div>',unsafe_allow_html=True)
nav_bar("chart")

if not scan:
    st.info("Run the scanner from Dashboard first.")
    st.stop()

st.markdown(f'<div class="mobile-date">Data date: {esc(scan.get("data_date","-"))} • Benchmark: NIFTY 50</div>',unsafe_allow_html=True)
latest=scan["sector_df"].copy(); histories=scan["sector_histories"]
colors={"LEADING":"#16a34a","IMPROVING":"#2563eb","WEAKENING":"#f59e0b","LAGGING":"#dc2626"}

# Determine a stable chart range from all current points + Top-5 trails.
xs = pd.to_numeric(latest["RS_Ratio"], errors="coerce").dropna().tolist()
ys = pd.to_numeric(latest["RS_Momentum"], errors="coerce").dropna().tolist()
for _,r in latest.head(5).iterrows():
    h=histories.get(str(r["Sector"]))
    if isinstance(h,pd.DataFrame) and not h.empty:
        t=h.tail(8)
        xs += pd.to_numeric(t["RS_Ratio"], errors="coerce").dropna().tolist()
        ys += pd.to_numeric(t["RS_Momentum"], errors="coerce").dropna().tolist()

xs = xs + [100.0]; ys = ys + [100.0]
xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
xpad=max(3.0,(xmax-xmin)*0.08); ypad=max(3.0,(ymax-ymin)*0.08)
xmin-=xpad; xmax+=xpad; ymin-=ypad; ymax+=ypad

fig=go.Figure()

# Four clearly separated RRG quadrants.
fig.add_shape(type="rect",x0=100,x1=xmax,y0=100,y1=ymax,fillcolor="rgba(22,163,74,0.10)",line_width=0,layer="below")
fig.add_shape(type="rect",x0=xmin,x1=100,y0=100,y1=ymax,fillcolor="rgba(37,99,235,0.10)",line_width=0,layer="below")
fig.add_shape(type="rect",x0=100,x1=xmax,y0=ymin,y1=100,fillcolor="rgba(245,158,11,0.10)",line_width=0,layer="below")
fig.add_shape(type="rect",x0=xmin,x1=100,y0=ymin,y1=100,fillcolor="rgba(220,38,38,0.10)",line_width=0,layer="below")

# Quadrant labels positioned away from the data center.
fig.add_annotation(x=xmax,y=ymax,text="LEADING",showarrow=False,xanchor="right",yanchor="top",font=dict(size=11,color="#16a34a"))
fig.add_annotation(x=xmin,y=ymax,text="IMPROVING",showarrow=False,xanchor="left",yanchor="top",font=dict(size=11,color="#3b82f6"))
fig.add_annotation(x=xmax,y=ymin,text="WEAKENING",showarrow=False,xanchor="right",yanchor="bottom",font=dict(size=11,color="#f59e0b"))
fig.add_annotation(x=xmin,y=ymin,text="LAGGING",showarrow=False,xanchor="left",yanchor="bottom",font=dict(size=11,color="#ef4444"))

# All current sector bullets.
for q,g in latest.groupby("Quadrant"):
    fig.add_trace(go.Scatter(
        x=g["RS_Ratio"],y=g["RS_Momentum"],mode="markers",
        marker=dict(size=8,color=colors.get(q,"#94a3b8")),
        text=[pretty_sector(v) for v in g["Sector"]],
        hovertemplate="%{text}<br>RS Ratio %{x:.2f}<br>RS Momentum %{y:.2f}<extra></extra>",
        showlegend=False
    ))

# Top-5 real 8-day tails.
label_shifts=[16,-16,16,-16,16]
for idx,(_,r) in enumerate(latest.head(5).iterrows()):
    raw_name=str(r["Sector"]); display_name=pretty_sector(raw_name); h=histories.get(raw_name)
    if isinstance(h,pd.DataFrame) and not h.empty:
        t=h.tail(8)
        fig.add_trace(go.Scatter(
            x=t["RS_Ratio"],y=t["RS_Momentum"],mode="lines+markers",
            line=dict(width=2),marker=dict(size=5),name=display_name,
            hovertemplate=display_name+"<br>RS Ratio %{x:.2f}<br>RS Momentum %{y:.2f}<extra></extra>"
        ))
        fig.add_annotation(
            x=float(t["RS_Ratio"].iloc[-1]),y=float(t["RS_Momentum"].iloc[-1]),
            text=display_name,showarrow=False,yshift=label_shifts[idx % len(label_shifts)],font=dict(size=10)
        )

fig.add_vline(x=100,line_dash="dash",line_width=1,line_color="rgba(148,163,184,.65)")
fig.add_hline(y=100,line_dash="dash",line_width=1,line_color="rgba(148,163,184,.65)")
fig.update_xaxes(range=[xmin,xmax],title="RS Ratio",gridcolor="rgba(148,163,184,.20)")
fig.update_yaxes(range=[ymin,ymax],title="RS Momentum",gridcolor="rgba(148,163,184,.20)")
fig.update_layout(
    height=610,
    margin=dict(l=18,r=18,t=25,b=45),
    legend=dict(orientation="h",y=-.18),
    hovermode="closest",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)"
)
st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"responsive":True})
st.caption("Four colored quadrants • All sectors = current position • Top 5 = 8-day rotation trail")
