import html
import math
import pandas as pd
import streamlit as st


def inject_css():
    st.markdown("""
    <style>
    .block-container{max-width:680px;padding-top:.55rem;padding-left:.75rem;padding-right:.75rem;padding-bottom:2rem}
    [data-testid="stSidebar"]{display:none}
    .mobile-title{font-size:1.42rem;font-weight:900;line-height:1.25;margin:.15rem 0 .12rem 0}
    .mobile-date{color:#64748b;font-size:.82rem;margin-bottom:.45rem}
    .section-title{font-size:.96rem;font-weight:900;letter-spacing:.02rem;margin-top:.9rem;margin-bottom:.38rem}
    .card{background:var(--secondary-background-color);border:1px solid rgba(120,130,150,.25);border-radius:13px;padding:.68rem .78rem;margin-bottom:.55rem;box-shadow:0 1px 3px rgba(15,23,42,.04)}
    .card-buy{border-left:5px solid #16a34a}.card-info{border-left:5px solid #2563eb}.card-intra{border-left:5px solid #7c3aed}
    .stock{font-size:1.08rem;font-weight:900;display:flex;align-items:baseline;gap:.32rem}.sector{color:#64748b;font-size:.78rem;margin-top:.08rem}.rank{font-weight:900;flex:0 0 auto}
    .kv{display:grid;grid-template-columns:1fr auto;gap:.12rem .65rem;margin-top:.42rem;font-size:.83rem}
    .kv .label{color:#64748b}.kv .value{font-weight:750;text-align:right}
    .signal{display:inline-block;margin-top:.45rem;padding:.27rem .46rem;border-radius:7px;font-weight:850;font-size:.79rem}
    .signal-buy{background:rgba(22,163,74,.13);color:#16a34a}.signal-dip{background:rgba(245,158,11,.15);color:#d97706}
    .q-leading{color:#16a34a;font-weight:850}.q-improving{color:#2563eb;font-weight:850}.q-weakening{color:#d97706;font-weight:850}.q-lagging{color:#dc2626;font-weight:850}
    div.stButton>button{width:100%;font-weight:850;border-radius:11px}
    /* Compact top navigation */
    div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]){gap:.30rem}
    </style>
    """, unsafe_allow_html=True)


def nav_bar(active="dashboard"):
    cols = st.columns(3, gap="small")
    labels = [
        ("dashboard", "🏠 Dashboard", "app.py"),
        ("intraday", "⚡ Intraday", "pages/Intraday.py"),
        ("chart", "📊 Chart", "pages/Chart.py"),
    ]
    for col, (key, label, target) in zip(cols, labels):
        with col:
            text = f"● {label}" if key == active else label
            if st.button(text, key=f"nav_{active}_{key}", use_container_width=True):
                st.switch_page(target)


def pretty_sector(x):
    """Presentation-only cleanup. Internal sector keys are never changed."""
    raw = str(x if x is not None else "-").strip()
    aliases = {
        "FINANCIAL_SERVICES_25_50": "FINANCIAL SERVICES 25/50",
        "FINANCIAL_SERVICES_EX_BANK": "FINANCIAL SERVICES EX-BANK",
        "MIDSMALL_IT_TELECOM": "MIDSMALL IT & TELECOM",
        "OIL_GAS": "OIL & GAS",
        "COMMERCIAL_TRANSPORT_SERVICES": "COMMERCIAL TRANSPORT",
        "CONSUMER_DURABLES": "CONSUMER DURABLES",
        "PRIVATE_BANK": "PRIVATE BANK",
        "PSU_BANK": "PSU BANK",
    }
    if raw in aliases:
        return aliases[raw]
    s = raw.replace("_", " ").replace("25 50", "25/50")
    return " ".join(s.split())


def esc(x): return html.escape(str(x if x is not None else "-"))
def safe(row,key,default="-"):
    try:
        v=row.get(key,default)
        return default if pd.isna(v) else v
    except Exception:return default

def num(x,d=1):
    try:return f"{float(x):,.{d}f}"
    except Exception:return "-"
def money(x):
    try:return f"₹{float(x):,.2f}"
    except Exception:return "-"
def qhtml(q):
    q=str(q or "-").upper(); c={"LEADING":"q-leading","IMPROVING":"q-improving","WEAKENING":"q-weakening","LAGGING":"q-lagging"}.get(q,"")
    return f'<span class="{c}">{esc(q)}</span>'
def section(title): st.markdown(f'<div class="section-title">{esc(title)}</div>',unsafe_allow_html=True)
def metrics(items): return '<div class="kv">'+''.join(f'<div class="label">{esc(a)}</div><div class="value">{b}</div>' for a,b in items)+'</div>'
def card(body,kind="info"): st.markdown(f'<div class="card card-{kind}">{body}</div>',unsafe_allow_html=True)
