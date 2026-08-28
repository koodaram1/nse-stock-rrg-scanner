import streamlit as st
from scanner_engine import run_scanner
from mobile_ui import inject_css, safe, num, money, qhtml, section, metrics, card, esc, nav_bar, pretty_sector

def best_display_sector(membership_text, sector_df):
    """Presentation only: choose the highest-ranked current sector membership."""
    parts=[p.strip() for p in str(membership_text or "").split("|") if p.strip()]
    if not parts:
        return "-"
    try:
        rank_map={str(r["Sector"]): float(r["Rank"]) for _,r in sector_df.iterrows()}
        valid=[(rank_map[p],p) for p in parts if p in rank_map]
        if valid:
            return min(valid,key=lambda x:x[0])[1]
    except Exception:
        pass
    return parts[0]

st.set_page_config(page_title="NSE Stock RRG",page_icon="📈",layout="centered",initial_sidebar_state="collapsed")
inject_css()
scan=st.session_state.get("scan")
run_date=scan.get("run_date") if scan else "-"
run_time=scan.get("run_time") if scan else ""
st.markdown('<div class="mobile-title">NSE STOCK RRG</div>',unsafe_allow_html=True)
st.markdown(f'<div class="mobile-date">Swing + Intraday • {esc(run_date)} {esc(run_time)}</div>',unsafe_allow_html=True)
nav_bar("dashboard")

if st.button("🔄 RUN SCANNER",type="primary"):
    bar=st.progress(0,text="Starting scanner...")
    def prog(v,text): bar.progress(max(0,min(100,int(v*100))),text=text)
    try:
        st.session_state["scan"]=run_scanner(progress=prog)
        scan=st.session_state["scan"]
        bar.empty(); st.success("Scanner completed.")
    except Exception as e:
        bar.empty(); st.error(f"Scanner could not complete: {e}"); st.stop()

if not scan:
    st.caption("Tap RUN SCANNER to load the latest mobile shortlist.")
    st.stop()

st.caption(f'Data date: {scan.get("data_date","-")} • Stocks: {scan.get("successful_downloads",0)}/{scan.get("universe_count",500)} • Benchmark: NIFTY 50')

section("🔥 TOP 5 SECTORS")
for _,r in scan["sector_df"].head(5).iterrows():
    body=f'<div class="stock"><span class="rank">#{int(r["Rank"])}</span><span>{esc(pretty_sector(r["Sector"]))}</span></div><div class="sector">{qhtml(r["Quadrant"])}</div>'+metrics([("RS Ratio",num(r["RS_Ratio"],2)),("RS Momentum",num(r["RS_Momentum"],2))])
    card(body,"info")

section("📈 SWING SUITABLE")
swing=scan["swing"].head(10)
if swing.empty:
    st.info("No qualified BUY NOW / BUY ON DIP Swing candidate now.")
else:
    for i,(_,r) in enumerate(swing.iterrows(),start=1):
        action=str(safe(r,"Action","-")); sigclass="signal-buy" if action=="BUY NOW" else "signal-dip"
        body=f'<div class="stock"><span class="rank">#{i}</span><span>{esc(safe(r,"Symbol"))}</span></div><div class="sector">{esc(pretty_sector(best_display_sector(safe(r,"Sector"), scan["sector_df"])))} • {qhtml(safe(r,"RRG_Quadrant"))}</div>'+metrics([("Score",num(safe(r,"Opportunity_Score"),1)),("Confidence",esc(safe(r,"Confidence"))),("Price",money(safe(r,"Current_Price"))),("Buy Zone",esc(safe(r,"Buy_Zone"))),("SL",money(safe(r,"Stop_Loss"))),("T1",money(safe(r,"Target_1")))])+f'<div class="signal {sigclass}">{esc(action)}</div>'
        card(body,"buy")

st.caption("Screening only. Intraday shortlist is based mainly on daily data; confirm entries with live broker/exchange data.")
