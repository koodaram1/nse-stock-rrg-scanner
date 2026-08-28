# NSE STOCK RRG MOBILE V1.0

Very-light mobile Streamlit version of the verified NSE Professional RRG stock scanner.

## Mobile pages
- **Dashboard**: Top 5 sectors + up to Top 10 qualified Swing BUY NOW / BUY ON DIP stocks.
- **Intraday**: Top 10 intraday-suitable stocks from the existing daily-data RRG/Opportunity/Intraday scoring framework.
- **Chart**: one interactive Sector RRG chart; all current sector bullets plus real 8-day trails for Top 5 sectors.

## Architecture
The phone does not calculate the scanner. Pressing **RUN SCANNER** runs `scanner_engine.py` on the Streamlit server. Results are held in `st.session_state`. The Chart and Intraday pages reuse the completed scan and do not download the universe again.

No Google Drive is required by the mobile app. Runtime data is temporary.

## Deployment — same approach as the ETF mobile app
1. Create a new GitHub repository, e.g. `nse-stock-rrg-mobile`.
2. Upload this package contents exactly, keeping `data/`, `pages/`, and `.streamlit/` folders.
3. Open Streamlit Community Cloud and create a new app from that repository.
4. Main file path: `app.py`.
5. Deploy.
6. Open the Streamlit URL on iPhone/Android and tap **RUN SCANNER**.

## Important
- Benchmark: NIFTY 50.
- Core RRG parameters: RS smoothing 10, momentum period 10, normalization 50 — matching the verified desktop scanner.
- Swing candidates are strict `BUY NOW` or `BUY ON DIP` outputs only; the mobile page does not force 10 names.
- Intraday is a **candidate shortlist based mainly on daily data**, not a live entry trigger. Confirm live price, volume, spread, news and broker execution conditions before trading.
- `data/stock_master.csv` and `data/sector_membership.csv` are copied from the verified final desktop backup. When the desktop universe/mapping is formally updated, replace these two files in the mobile repository too.
