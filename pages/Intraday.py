import streamlit as st
from mobile_ui import inject_css,safe,num,money,qhtml,section,metrics,card,esc,nav_bar,pretty_sector

st.set_page_config(page_title="NSE Stock RRG — Intraday",page_icon="⚡",layout="centered",initial_sidebar_state="collapsed")
inject_css(); scan=st.session_state.get("scan")
st.markdown('<div class="mobile-title">NSE STOCK RRG — INTRADAY</div>',unsafe_allow_html=True)
nav_bar("intraday")

if not scan:
    st.info("Run the scanner from Dashboard first.")
    st.stop()

st.markdown(f'<div class="mobile-date">Data date: {esc(scan.get("data_date","-"))}</div>',unsafe_allow_html=True)
section("⚡ TOP 10 INTRADAY SUITABLE")
df=scan["intraday"].head(10)
if df.empty:
    st.info("No qualified Intraday shortlist now.")
else:
    for _,r in df.iterrows():
        body=f'<div class="stock"><span class="rank">#{int(safe(r,"Intraday_Rank",0))}</span>{esc(safe(r,"Symbol"))}</div><div class="sector">{esc(pretty_sector(safe(r,"Best_Sector")))} • Sector {qhtml(safe(r,"Sector_Quadrant"))}</div>'+metrics([("Intraday Score",num(safe(r,"Intraday_Score"),1)),("Opportunity",num(safe(r,"Opportunity_Score"),1)),("Stock RRG",qhtml(safe(r,"Stock_Quadrant"))),("Beta 60D",num(safe(r,"Beta_60D"),2)),("Avg Value 20D",f'₹{num(safe(r,"Avg_Traded_Value_20D_Cr"),2)} Cr'),("Price",money(safe(r,"Close")))])
        card(body,"intra")
st.caption("Daily-data candidate shortlist — confirm actual intraday entry with live price, volume, spread and market conditions.")
