import math
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from mobile_ui import inject_css,esc,qhtml
st.set_page_config(page_title="NSE Stock RRG — Sector Chart",page_icon="📊",layout="centered",initial_sidebar_state="collapsed")
inject_css(); scan=st.session_state.get("scan")
st.markdown('<div class="mobile-title">NSE SECTOR RRG CHART</div>',unsafe_allow_html=True)
if not scan: st.info("Run the scanner from Dashboard first."); st.page_link("app.py",label="← DASHBOARD"); st.stop()
st.markdown(f'<div class="mobile-date">Data date: {esc(scan.get("data_date","-"))} • Benchmark: NIFTY 50</div>',unsafe_allow_html=True)
latest=scan["sector_df"].copy(); histories=scan["sector_histories"]
colors={"LEADING":"#16a34a","IMPROVING":"#2563eb","WEAKENING":"#f59e0b","LAGGING":"#dc2626"}
fig=go.Figure()
# all current bullets
for q,g in latest.groupby("Quadrant"):
    fig.add_trace(go.Scatter(x=g["RS_Ratio"],y=g["RS_Momentum"],mode="markers",marker=dict(size=8,color=colors.get(q,"#94a3b8")),text=g["Sector"],hovertemplate="%{text}<br>RS Ratio %{x:.2f}<br>RS Momentum %{y:.2f}<extra></extra>",showlegend=False))
# top5 real 8-day tails
for _,r in latest.head(5).iterrows():
    name=str(r["Sector"]); h=histories.get(name)
    if isinstance(h,pd.DataFrame) and not h.empty:
        t=h.tail(8)
        fig.add_trace(go.Scatter(x=t["RS_Ratio"],y=t["RS_Momentum"],mode="lines+markers",line=dict(width=2),marker=dict(size=5),name=name,hovertemplate=name+"<br>RS Ratio %{x:.2f}<br>RS Momentum %{y:.2f}<extra></extra>"))
        fig.add_annotation(x=float(t["RS_Ratio"].iloc[-1]),y=float(t["RS_Momentum"].iloc[-1]),text=name,showarrow=False,yshift=13,font=dict(size=10))
fig.add_vline(x=100,line_dash="dash",line_width=1); fig.add_hline(y=100,line_dash="dash",line_width=1)
fig.update_layout(height=610,margin=dict(l=18,r=18,t=25,b=25),xaxis_title="RS Ratio",yaxis_title="RS Momentum",legend=dict(orientation="h",y=-.18),hovermode="closest")
st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"responsive":True})
st.caption("All sectors = current position • Top 5 = 8-day rotation trail")
st.page_link("app.py",label="← DASHBOARD",use_container_width=True)
st.page_link("pages/Intraday.py",label="⚡ INTRADAY",use_container_width=True)
