"""
NSE Stock + Sector RRG Mobile Scanner
Version: V1.0

Purpose: very-light Streamlit/mobile presentation while preserving the core
RRG, Opportunity Score V2, Actionable Swing, and Intraday Top-20 logic from
the verified NSE Professional RRG desktop scanner.

Mobile runtime does not use Google Drive. Data is downloaded into memory and
results are returned to Streamlit session_state.
"""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import math
import re
import time

import numpy as np
import pandas as pd
import yfinance as yf

RS_SMOOTHING = 10
MOMENTUM_PERIOD = 10
NORMALIZATION_PERIOD = 50
DATA_START_DATE = "2024-01-01"
BATCH_SIZE = 50


def _calculate_rrg(price_series, benchmark_series):
    df = pd.concat([
        price_series.rename("Price"),
        benchmark_series.rename("NIFTY50")
    ], axis=1, join="inner").dropna()
    if len(df) < 150:
        return None
    df["RS"] = df["Price"] / df["NIFTY50"]
    df["RS_Smoothed"] = df["RS"].rolling(RS_SMOOTHING).mean()
    df["RS_Deviation"] = df["RS"] / df["RS_Smoothed"] - 1
    rs_std = df["RS_Deviation"].rolling(NORMALIZATION_PERIOD).std().replace(0, np.nan)
    df["RS_Ratio"] = 100 + (df["RS_Deviation"] / rs_std) * 10
    momentum_change = df["RS_Ratio"].pct_change(MOMENTUM_PERIOD)
    momentum_mean = momentum_change.rolling(NORMALIZATION_PERIOD).mean()
    momentum_std = momentum_change.rolling(NORMALIZATION_PERIOD).std().replace(0, np.nan)
    df["RS_Momentum"] = 100 + ((momentum_change - momentum_mean) / momentum_std) * 10
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["RS_Ratio", "RS_Momentum"])
    if df.empty:
        return None
    conditions = [
        (df["RS_Ratio"] >= 100) & (df["RS_Momentum"] >= 100),
        (df["RS_Ratio"] >= 100) & (df["RS_Momentum"] < 100),
        (df["RS_Ratio"] < 100) & (df["RS_Momentum"] < 100),
        (df["RS_Ratio"] < 100) & (df["RS_Momentum"] >= 100),
    ]
    df["Quadrant"] = np.select(conditions, ["LEADING", "WEAKENING", "LAGGING", "IMPROVING"], default="UNKNOWN")
    return df


def _calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _calculate_atr(high, low, close, period=10):
    previous_close = close.shift(1)
    tr = pd.concat([
        high-low,
        (high-previous_close).abs(),
        (low-previous_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()


def _calculate_supertrend(df, period=10, multiplier=3):
    # Numpy loop: same desktop rules, much faster for a 500-stock mobile scan.
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    atr = _calculate_atr(high, low, close, period).astype(float)
    hl2 = (high + low) / 2.0
    ub = (hl2 + multiplier * atr).to_numpy(copy=True)
    lb = (hl2 - multiplier * atr).to_numpy(copy=True)
    c = close.to_numpy(copy=False)
    uf = ub.copy(); lf = lb.copy()
    direction = np.empty(len(df), dtype=np.int8)
    st = np.empty(len(df), dtype=float)
    direction[0] = 1
    st[0] = lb[0]
    for i in range(1, len(df)):
        if not (ub[i] < uf[i-1] or c[i-1] > uf[i-1]):
            uf[i] = uf[i-1]
        if not (lb[i] > lf[i-1] or c[i-1] < lf[i-1]):
            lf[i] = lf[i-1]
        if c[i] > uf[i-1]:
            direction[i] = 1
        elif c[i] < lf[i-1]:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
        st[i] = lf[i] if direction[i] == 1 else uf[i]
    return pd.Series(st, index=df.index), pd.Series(direction, index=df.index)


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i+size]


def _clean_ohlcv(df):
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    req = ["Open", "High", "Low", "Close", "Volume"]
    if any(c not in df.columns for c in req):
        return None
    out = df[req].copy().dropna(subset=["Close"])
    if out.empty:
        return None
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out


def _download_histories(stock_universe, progress=None):
    histories = {}
    failed = []
    symbols = stock_universe["Yahoo_Symbol"].dropna().astype(str).tolist()
    batches = list(_chunks(symbols, BATCH_SIZE))
    for bno, batch in enumerate(batches, start=1):
        if progress:
            progress((bno-1)/max(1,len(batches)), f"Downloading stocks — batch {bno}/{len(batches)}")
        try:
            bd = yf.download(
                tickers=batch, start=DATA_START_DATE, interval="1d", auto_adjust=True,
                group_by="ticker", threads=True, progress=False
            )
        except Exception:
            bd = None
        for sym in batch:
            ticker = sym.replace(".NS", "")
            df = None
            try:
                if bd is not None and not bd.empty:
                    if isinstance(bd.columns, pd.MultiIndex):
                        level0 = bd.columns.get_level_values(0)
                        if sym in level0:
                            df = bd[sym].copy()
                        elif ticker in level0:
                            df = bd[ticker].copy()
                    else:
                        df = bd.copy()
                    df = _clean_ohlcv(df)
            except Exception:
                df = None
            if df is None:
                try:
                    one = yf.download(sym, start=DATA_START_DATE, interval="1d", auto_adjust=True,
                                      progress=False, threads=False)
                    df = _clean_ohlcv(one)
                except Exception:
                    df = None
            if df is None:
                failed.append(ticker)
            else:
                histories[ticker] = df
    if progress:
        progress(1.0, "Stock download completed")
    return histories, failed


def _download_benchmark():
    b = yf.download("^NSEI", start=DATA_START_DATE, interval="1d", auto_adjust=True,
                    progress=False, threads=False)
    b = _clean_ohlcv(b)
    if b is None:
        raise RuntimeError("NIFTY 50 benchmark download failed")
    return b["Close"].astype(float).dropna()


def _opportunity_score(row, sector_lookup):
    score = 0.0
    quadrant = row["Quadrant"]
    rs_ratio = row["RS_Ratio"]
    rs_momentum = row["RS_Momentum"]
    technical_score = row["Technical_Score"]
    supertrend = row["Supertrend_Signal"]
    rsi = row["RSI14"]
    transition = row["Transition"]
    rv = row["RS_Ratio_Velocity_5D"]
    mv = row["RS_Momentum_Velocity_5D"]
    score += {"LEADING":20,"IMPROVING":14,"WEAKENING":6,"LAGGING":0}.get(quadrant,0)
    score += np.clip((rs_ratio-100)*0.5,0,10)
    score += np.clip((rs_momentum-100)*0.5,0,10)
    if pd.notna(technical_score): score += (float(technical_score)/5)*20
    if supertrend == "BUY": score += 8
    if pd.notna(rsi):
        if 50 <= rsi <= 62: score += 7
        elif 62 < rsi <= 68: score += 6
        elif 45 <= rsi < 50: score += 4
        elif 68 < rsi <= 72: score += 3
        elif 40 <= rsi < 45: score += 2
        elif rsi > 75: score -= 3
    score += {
        "IMPROVING → LEADING":10,"WEAKENING → LEADING":8,"LAGGING → LEADING":7,
        "LAGGING → IMPROVING":6,"WEAKENING → IMPROVING":5,
        "LEADING → WEAKENING":-6,"IMPROVING → LAGGING":-8,
        "WEAKENING → LAGGING":-8,"LEADING → LAGGING":-10,
    }.get(transition,0)
    vp = 0
    if rv > 2: vp += 5
    elif rv > 0: vp += 3
    elif rv < -2: vp -= 4
    elif rv < 0: vp -= 2
    if mv > 4: vp += 10
    elif mv > 1: vp += 6
    elif mv > 0: vp += 3
    elif mv < -4: vp -= 8
    elif mv < 0: vp -= 3
    score += np.clip(vp,-10,15)
    best_sector_points = 0
    for sector_name in [x.strip() for x in str(row["Sector"]).split("|")]:
        if sector_name not in sector_lookup: continue
        q = sector_lookup[sector_name]["Quadrant"]
        best_sector_points = max(best_sector_points, {"LEADING":10,"IMPROVING":7,"WEAKENING":3}.get(q,0))
    score += best_sector_points
    if quadrant == "LEADING" and mv < -5: score -= 8
    if quadrant == "WEAKENING" and mv < 0: score -= 5
    return round(float(np.clip(score,0,100)),2)


def _opportunity_signal(score):
    if score >= 90: return "EXCEPTIONAL"
    if score >= 80: return "STRONG"
    if score >= 70: return "GOOD"
    if score >= 60: return "WATCH"
    if score >= 50: return "NEUTRAL"
    return "WEAK"


def _best_sector(text, sector_lookup):
    matches=[]
    for part in re.split(r"\s*[|,;/]\s*", str(text or "")):
        p=part.strip()
        if p in sector_lookup and pd.notna(sector_lookup[p].get("Rank")):
            matches.append((float(sector_lookup[p]["Rank"]), p, sector_lookup[p]["Quadrant"]))
    if not matches: return "", np.nan, ""
    best=min(matches,key=lambda x:x[0])
    return best[1],best[0],best[2]


def _build_trade_setups(opportunity_df, histories):
    rows=[]
    for _,opp in opportunity_df.iterrows():
        symbol=opp["Symbol"]
        price_df=histories.get(symbol)
        if price_df is None or len(price_df)<60: continue
        atr14=_calculate_atr(price_df["High"],price_df["Low"],price_df["Close"],period=14)
        ema20=price_df["Close"].ewm(span=20,adjust=False).mean()
        close=float(price_df["Close"].iloc[-1]); current_atr=float(atr14.iloc[-1]); current_ema20=float(ema20.iloc[-1])
        if not np.isfinite(current_atr) or current_atr<=0: continue
        st_value=np.nan
        try:
            temp_st,_=_calculate_supertrend(price_df.copy(),period=10,multiplier=3)
            st_value=float(temp_st.iloc[-1])
        except Exception: pass
        swing_low_20=float(price_df["Low"].tail(20).min())
        entry_low=close-0.25*current_atr; entry_high=close+0.15*current_atr
        atr_stop=close-1.50*current_atr
        candidates=[atr_stop,swing_low_20]
        if pd.notna(st_value) and st_value<close: candidates.append(st_value)
        valid=[x for x in candidates if pd.notna(x) and x<close]
        technical_stop=max(valid) if valid else atr_stop
        minimum_stop=close-0.75*current_atr
        stop_loss=min(technical_stop,minimum_stop)
        risk_per_share=close-stop_loss
        if risk_per_share<=0: continue
        risk_percent=risk_per_share/close*100
        target1=close+1.5*risk_per_share; target2=close+2.5*risk_per_share
        ema_dist=(close-current_ema20)/current_atr
        score=float(opp["Opportunity_Score"]); rsi=opp["RSI14"]; st=opp["Supertrend_Signal"]
        q=opp["Quadrant"]; mv=opp["RS_Momentum_Velocity_5D"]
        status="WATCH"
        if st!="BUY" or q=="LAGGING": status="WAIT"
        elif pd.notna(rsi) and rsi>72: status="WAIT FOR PULLBACK"
        elif pd.notna(ema_dist) and ema_dist>1.50: status="WAIT FOR PULLBACK"
        elif score>=85 and q in ["LEADING","IMPROVING"] and mv>0: status="ENTER ZONE"
        elif score>=75 and q in ["LEADING","IMPROVING"]: status="WATCH FOR ENTRY"
        if score>=90 and status=="ENTER ZONE": quality="A+"
        elif score>=85 and status=="ENTER ZONE": quality="A"
        elif score>=75: quality="B"
        elif score>=65: quality="C"
        else: quality="LOW"
        rows.append({
            "Opportunity_Rank":opp["Opportunity_Rank"],"Sector":opp["Sector"],"Stock":opp["Stock"],"Symbol":symbol,
            "Quadrant":q,"Opportunity_Score":score,"Close":close,"ATR14":current_atr,"EMA20":current_ema20,
            "EMA20_Distance_ATR":ema_dist,"RSI14":rsi,"Supertrend_Signal":st,
            "RS_Ratio_Velocity_5D":opp["RS_Ratio_Velocity_5D"],"RS_Momentum_Velocity_5D":mv,
            "Entry_Zone_Low":entry_low,"Entry_Zone_High":entry_high,"Stop_Loss":stop_loss,"Risk_Percent":risk_percent,
            "Target_1":target1,"Target_2":target2,"Entry_Status":status,"Trade_Quality":quality,
        })
    return pd.DataFrame(rows)


def _build_actionable(trades):
    rows=[]
    for _,row in trades.iterrows():
        score=row["Opportunity_Score"]; status=row["Entry_Status"]; quality=row["Trade_Quality"]
        q=row["Quadrant"]; rsi=row["RSI14"]; st=row["Supertrend_Signal"]
        rv=row["RS_Ratio_Velocity_5D"]; mv=row["RS_Momentum_Velocity_5D"]
        if status=="ENTER ZONE" and quality in ["A+","A"] and score>=85 and st=="BUY" and q in ["LEADING","IMPROVING"]:
            action="BUY NOW"
        elif status=="WAIT FOR PULLBACK" and score>=75 and st=="BUY": action="BUY ON DIP"
        elif status in ["WATCH FOR ENTRY","WATCH"] and score>=65: action="WATCH"
        else: action="AVOID"
        cs=0
        cs += 3 if score>=90 else 2 if score>=80 else 1 if score>=70 else 0
        if st=="BUY": cs+=2
        cs += 2 if q=="LEADING" else 1 if q=="IMPROVING" else 0
        cs += 2 if mv>5 else 1 if mv>0 else 0
        if pd.notna(rsi) and 50<=rsi<=68: cs+=1
        confidence="VERY HIGH" if cs>=8 else "HIGH" if cs>=6 else "MEDIUM" if cs>=4 else "LOW"
        reasons=[]
        if q=="LEADING": reasons.append("RRG Leading")
        elif q=="IMPROVING": reasons.append("RRG Improving")
        if rv>0: reasons.append("RS Ratio rising")
        if mv>0: reasons.append("RS Momentum rising")
        if st=="BUY": reasons.append("Supertrend BUY")
        if pd.notna(rsi) and 50<=rsi<=68: reasons.append("RSI healthy")
        if status=="ENTER ZONE": reasons.append("Price in entry zone")
        if status=="WAIT FOR PULLBACK": reasons.append("Price extended")
        rows.append({
            "Stock":row["Stock"],"Symbol":row["Symbol"],"Sector":row["Sector"],"Action":action,"Confidence":confidence,
            "Current_Price":row["Close"],"Buy_Zone":f'{row["Entry_Zone_Low"]:.2f} - {row["Entry_Zone_High"]:.2f}',
            "Stop_Loss":row["Stop_Loss"],"Target_1":row["Target_1"],"Target_2":row["Target_2"],
            "Risk_Percent":row["Risk_Percent"],"Opportunity_Score":score,"Trade_Quality":quality,
            "RRG_Quadrant":q,"RSI14":rsi,"Supertrend":st,"Reason":" | ".join(reasons)
        })
    out=pd.DataFrame(rows)
    if out.empty: return out
    ap={"BUY NOW":1,"BUY ON DIP":2,"WATCH":3,"AVOID":4}; cp={"VERY HIGH":1,"HIGH":2,"MEDIUM":3,"LOW":4}
    out["Action_Priority"]=out["Action"].map(ap).fillna(99); out["Confidence_Priority"]=out["Confidence"].map(cp).fillna(99)
    out=out.sort_values(["Action_Priority","Confidence_Priority","Opportunity_Score"],ascending=[True,True,False]).reset_index(drop=True)
    out.insert(0,"Trade_Rank",range(1,len(out)+1))
    return out


def _minmax(series):
    s=pd.to_numeric(series,errors="coerce")
    if s.notna().sum()==0: return pd.Series(0,index=series.index)
    mn,mx=s.min(),s.max()
    if mx==mn: return pd.Series(1,index=series.index)
    return ((s-mn)/(mx-mn)).clip(0,1)


def _beta_score(beta):
    if pd.isna(beta): return 0.30
    if 0.90<=beta<=1.80: return 1.00
    if 0.70<=beta<0.90 or 1.80<beta<=2.10: return 0.80
    if 0.50<=beta<0.70: return 0.55
    if 2.10<beta<=2.50: return 0.50
    return 0.25


def _quadrant_score(q):
    return {"LEADING":1.00,"IMPROVING":0.90,"WEAKENING":0.30,"LAGGING":0.10}.get(str(q).upper().strip(),0.40)


def _download_intraday_metrics(symbols):
    tickers=[s+".NS" for s in symbols]+["^NSEI"]
    try:
        px=yf.download(tickers,period="6mo",interval="1d",auto_adjust=False,progress=False,group_by="column",threads=True)
    except Exception:
        return pd.DataFrame()
    def get_series(field,ticker):
        try:
            if isinstance(px.columns,pd.MultiIndex) and field in px.columns.get_level_values(0):
                return px[field][ticker].dropna()
        except Exception: pass
        return pd.Series(dtype=float)
    nifty_close=get_series("Close","^NSEI"); nifty_ret=nifty_close.pct_change().dropna()
    rows=[]
    for symbol in symbols:
        ticker=symbol+".NS"; close=get_series("Close",ticker); volume=get_series("Volume",ticker)
        if len(close)<20:
            rows.append({"Symbol":symbol,"Beta_60D":np.nan,"Avg_Volume_20D":np.nan,"Avg_Traded_Value_20D_Cr":np.nan,"Close":np.nan,"EMA20":np.nan,"EMA50":np.nan,"Trend_Score":0}); continue
        close=close.astype(float); volume=volume.reindex(close.index).astype(float)
        current=float(close.iloc[-1]); ema20=float(close.ewm(span=20,adjust=False).mean().iloc[-1]); ema50=float(close.ewm(span=50,adjust=False).mean().iloc[-1]) if len(close)>=50 else np.nan
        avg_vol=float(volume.tail(20).mean()); avg_val=float((close*volume).tail(20).mean())/1_00_00_000
        sr=close.pct_change().dropna(); temp=pd.concat([sr.rename("stock"),nifty_ret.rename("market")],axis=1,join="inner").dropna().tail(60)
        beta=np.nan
        if len(temp)>=20 and temp["market"].var()!=0: beta=temp["stock"].cov(temp["market"])/temp["market"].var()
        trend=0.0
        if current>ema20: trend+=0.50
        if pd.notna(ema50) and current>ema50: trend+=0.30
        if pd.notna(ema50) and ema20>ema50: trend+=0.20
        rows.append({"Symbol":symbol,"Beta_60D":beta,"Avg_Volume_20D":avg_vol,"Avg_Traded_Value_20D_Cr":avg_val,"Close":current,"EMA20":ema20,"EMA50":ema50,"Trend_Score":trend})
    return pd.DataFrame(rows)


def _build_intraday(opportunity_df, sector_df):
    df=opportunity_df[["Stock","Symbol","Sector","Quadrant","RS_Ratio","RS_Momentum","Technical_Score","Opportunity_Score"]].copy()
    df.rename(columns={"Quadrant":"Stock_Quadrant"},inplace=True)
    sector_lookup={r["Sector"]:{"Rank":r["Rank"],"Quadrant":r["Quadrant"]} for _,r in sector_df.iterrows()}
    best=df["Sector"].apply(lambda x: pd.Series(_best_sector(x,sector_lookup),index=["Best_Sector","Sector_Rank","Sector_Quadrant"]))
    df=pd.concat([df,best],axis=1)
    filtered=df[df["Stock_Quadrant"].isin(["LEADING","IMPROVING"])].copy()
    if filtered["RS_Momentum"].notna().any(): filtered=filtered[filtered["RS_Momentum"]>100].copy()
    if len(filtered)<20: filtered=df.copy()
    filtered=filtered.sort_values("Opportunity_Score",ascending=False).head(60).copy()
    metrics=_download_intraday_metrics(filtered["Symbol"].dropna().unique().tolist())
    filtered=filtered.merge(metrics,on="Symbol",how="left")
    filtered["Opportunity_Component"]=_minmax(filtered["Opportunity_Score"])*20
    filtered["RRG_Component"]=(filtered["Stock_Quadrant"].apply(_quadrant_score)*0.40 + _minmax(filtered["RS_Ratio"])*0.30 + _minmax(filtered["RS_Momentum"])*0.30)*20
    # finalizer: only LEADING / IMPROVING best sector
    filtered=filtered[filtered["Sector_Quadrant"].isin(["LEADING","IMPROVING"])].copy()
    filtered["Sector_Component"]=filtered["Sector_Quadrant"].apply(lambda q: 1.0 if q=="LEADING" else 0.9 if q=="IMPROVING" else 0.0)*15
    filtered["Technical_Component"]=_minmax(filtered["Technical_Score"])*10
    filtered["Liquidity_Component"]=_minmax(np.log1p(filtered["Avg_Traded_Value_20D_Cr"].fillna(0)))*15
    filtered["Beta_Component"]=filtered["Beta_60D"].apply(_beta_score)*10
    filtered["Trend_Component"]=filtered["Trend_Score"].fillna(0)*10
    comps=["Opportunity_Component","RRG_Component","Sector_Component","Technical_Component","Liquidity_Component","Beta_Component","Trend_Component"]
    filtered["Intraday_Score"]=filtered[comps].fillna(0).sum(axis=1).round(2)
    filtered=filtered.sort_values(["Intraday_Score","Opportunity_Score"],ascending=[False,False]).head(20).reset_index(drop=True)
    filtered.insert(0,"Intraday_Rank",range(1,len(filtered)+1))
    return filtered


def _analyze(stock_universe, mapping, histories, benchmark_close, progress=None):
    # labels
    nifty500_symbols=set(stock_universe["Yahoo_Symbol"])
    mapping=mapping[mapping["Yahoo_Symbol"].isin(nifty500_symbols)].copy()
    sector_labels=(mapping.groupby("Yahoo_Symbol")["Sector"].agg(lambda x:" | ".join(sorted(set(x)))).reset_index())
    universe=stock_universe.merge(sector_labels,on="Yahoo_Symbol",how="left")
    universe["Sector"]=universe["Sector"].fillna("UNMAPPED")
    label_map={r["Yahoo_Symbol"].replace(".NS",""):(r["Stock_Name"],r["Sector"]) for _,r in universe.iterrows()}

    # stock rrg
    stock_rows=[]; stock_rrg_hist={}
    for idx,(ticker,h) in enumerate(histories.items(),start=1):
        if progress and idx%50==0: progress(min(0.95,idx/max(1,len(histories))),"Calculating stock RRG")
        rrg=_calculate_rrg(h["Close"],benchmark_close)
        if rrg is None or ticker not in label_map: continue
        stock_rrg_hist[ticker]=rrg
        latest=rrg.iloc[-1]; name,sector=label_map[ticker]
        stock_rows.append({"Date":rrg.index[-1],"Sector":sector,"Stock":name,"Symbol":ticker,"Close":latest["Price"],"RS_Ratio":latest["RS_Ratio"],"RS_Momentum":latest["RS_Momentum"],"Quadrant":latest["Quadrant"]})
    stock_df=pd.DataFrame(stock_rows)
    if stock_df.empty: raise RuntimeError("No stock RRG results generated")
    stock_df["Strength_Score"]=stock_df["RS_Ratio"]+stock_df["RS_Momentum"]
    stock_df=stock_df.sort_values("Strength_Score",ascending=False).reset_index(drop=True); stock_df["Rank"]=stock_df.index+1

    # sector rrg
    sec_rows=[]; sector_histories={}
    for sector in mapping["Sector"].dropna().unique():
        members=mapping[mapping["Sector"]==sector]
        arr=[]
        for _,r in members.iterrows():
            t=r["Yahoo_Symbol"].replace(".NS",""); h=histories.get(t)
            if h is None or len(h["Close"])<150: continue
            s=(h["Close"]/h["Close"].iloc[0])*100; s.name=t; arr.append(s)
        if not arr: continue
        sp=pd.concat(arr,axis=1).reindex(benchmark_close.index).ffill(limit=3)
        min_req=max(1,int(len(arr)*0.8)); sp=sp.dropna(thresh=min_req); syn=sp.mean(axis=1)
        sr=_calculate_rrg(syn,benchmark_close)
        if sr is None: continue
        sector_histories[sector]=sr
        latest=sr.iloc[-1]; sec_rows.append({"Sector":sector,"RS_Ratio":latest["RS_Ratio"],"RS_Momentum":latest["RS_Momentum"],"Quadrant":latest["Quadrant"]})
    sector_df=pd.DataFrame(sec_rows)
    if sector_df.empty: raise RuntimeError("No sector RRG results generated")
    sector_df["Strength_Score"]=sector_df["RS_Ratio"]+sector_df["RS_Momentum"]
    sector_df=sector_df.sort_values("Strength_Score",ascending=False).reset_index(drop=True); sector_df["Rank"]=sector_df.index+1
    sector_lookup={r["Sector"]:{"RS_Ratio":r["RS_Ratio"],"RS_Momentum":r["RS_Momentum"],"Quadrant":r["Quadrant"],"Rank":r["Rank"]} for _,r in sector_df.iterrows()}

    # technical + transition + velocity
    tech=[]
    for _,row in stock_df.iterrows():
        t=row["Symbol"]; h=histories.get(t)
        if h is None or len(h)<100: continue
        close=h["Close"].astype(float); ema20=close.ewm(span=20,adjust=False).mean(); ema50=close.ewm(span=50,adjust=False).mean(); rsi=_calculate_rsi(close)
        try: _,direction=_calculate_supertrend(h.copy()); st_buy=direction.iloc[-1]==1
        except Exception: st_buy=False
        latest=close.iloc[-1]; score=int(latest>ema20.iloc[-1])+int(latest>ema50.iloc[-1])+int(ema20.iloc[-1]>ema50.iloc[-1])+int(st_buy)+int(50<=rsi.iloc[-1]<=70)
        rr=stock_rrg_hist.get(t); transition="NO CHANGE"; signal="NEUTRAL"; rv=0.0; mv=0.0
        if rr is not None and len(rr)>=2:
            pq,cq=rr.iloc[-2]["Quadrant"],rr.iloc[-1]["Quadrant"]
            if pq!=cq:
                transition=f"{pq} → {cq}"
                signal="POSITIVE" if cq=="LEADING" or (pq=="LAGGING" and cq=="IMPROVING") else "CAUTION" if cq=="WEAKENING" else "NEGATIVE" if cq=="LAGGING" else "NEUTRAL"
        if rr is not None and len(rr)>=6:
            rv=float(rr.iloc[-1]["RS_Ratio"]-rr.iloc[-6]["RS_Ratio"]); mv=float(rr.iloc[-1]["RS_Momentum"]-rr.iloc[-6]["RS_Momentum"])
        tech.append({"Symbol":t,"EMA20":float(ema20.iloc[-1]),"EMA50":float(ema50.iloc[-1]),"RSI14":float(rsi.iloc[-1]),"Supertrend_Signal":"BUY" if st_buy else "SELL","Technical_Score":score,"Transition":transition,"Signal":signal,"RS_Ratio_Velocity_5D":rv,"RS_Momentum_Velocity_5D":mv})
    technical=pd.DataFrame(tech)
    opp=stock_df.merge(technical,on="Symbol",how="left")
    for col,default in [("Technical_Score",0),("RSI14",np.nan),("Supertrend_Signal","SELL"),("Transition","NO CHANGE"),("Signal","NEUTRAL"),("RS_Ratio_Velocity_5D",0.0),("RS_Momentum_Velocity_5D",0.0)]:
        if col not in opp: opp[col]=default
        else: opp[col]=opp[col].fillna(default) if default is not np.nan else opp[col]
    opp["Opportunity_Score"]=opp.apply(lambda r:_opportunity_score(r,sector_lookup),axis=1)
    opp["Opportunity_Signal"]=opp["Opportunity_Score"].apply(_opportunity_signal)
    opp=opp.sort_values("Opportunity_Score",ascending=False).reset_index(drop=True); opp["Opportunity_Rank"]=opp.index+1

    trades=_build_trade_setups(opp,histories); actionable=_build_actionable(trades)
    swing=actionable[actionable["Action"].isin(["BUY NOW","BUY ON DIP"])].head(10).copy() if not actionable.empty else pd.DataFrame()
    intraday=_build_intraday(opp,sector_df).head(10).copy()
    data_date=str(pd.to_datetime(benchmark_close.index[-1]).date())
    return {
        "run_date":datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"),
        "run_time":datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST"),
        "data_date":data_date,
        "universe_count":len(stock_universe),
        "successful_downloads":len(histories),
        "sector_df":sector_df,
        "sector_histories":sector_histories,
        "stock_df":stock_df,
        "opportunity_df":opp,
        "swing":swing,
        "intraday":intraday,
    }


def run_scanner(root_dir=None, progress=None):
    base=Path(__file__).resolve().parent
    stock_universe=pd.read_csv(base/"data"/"stock_master.csv").drop_duplicates("Yahoo_Symbol").reset_index(drop=True)
    mapping=pd.read_csv(base/"data"/"sector_membership.csv").drop_duplicates(["Sector","Yahoo_Symbol"]).reset_index(drop=True)
    if progress: progress(0.0,"Downloading NIFTY 50 benchmark")
    benchmark=_download_benchmark()
    histories,failed=_download_histories(stock_universe,progress=progress)
    if len(histories)<350:
        raise RuntimeError(f"Only {len(histories)} stock histories downloaded; scan stopped for data quality.")
    result=_analyze(stock_universe,mapping,histories,benchmark,progress=progress)
    result["failed_symbols"]=failed
    return result
