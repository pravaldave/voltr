import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── email config (global) ─────────────────────────────────
SENDER_EMAIL    = "noreply.voltr@gmail.com"
SENDER_PASSWORD = "rdnsikttgcaeqrje"

def send_alert_email(recipient, stock_name, trigger_desc, current_price, day_chg):
    try:
        msg       = MIMEMultipart("alternative")
        chg_color = "#4ade80" if day_chg >= 0 else "#f87171"
        chg_sign  = "+" if day_chg >= 0 else ""
        msg["Subject"] = f"Voltr Alert — {stock_name} triggered"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = recipient
        html = f"""
        <html>
        <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;
                     background:#0a0a0a;color:#f0f0f0;padding:40px 20px;margin:0">
          <div style="max-width:480px;margin:0 auto">
            <p style="font-size:13px;font-weight:600;color:#555;
                       letter-spacing:2px;margin:0 0 24px">VOLTR</p>
            <h1 style="font-size:24px;font-weight:600;color:#f0f0f0;
                        letter-spacing:-0.5px;margin:0 0 6px">Alert triggered</h1>
            <p style="font-size:13px;color:#555;margin:0 0 32px">
              {datetime.now().strftime("%d %b %Y · %I:%M %p")}
            </p>
            <div style="background:#141414;border:1px solid #1e1e1e;
                         border-radius:16px;padding:28px;margin-bottom:20px">
              <p style="font-size:13px;color:#555;margin:0 0 6px;
                         text-transform:uppercase;letter-spacing:1px">Stock</p>
              <p style="font-size:22px;font-weight:600;color:#f0f0f0;
                         margin:0 0 20px;letter-spacing:-0.3px">{stock_name}</p>
              <p style="font-size:13px;color:#555;margin:0 0 6px;
                         text-transform:uppercase;letter-spacing:1px">Trigger</p>
              <p style="font-size:15px;color:#f0f0f0;margin:0 0 20px;
                         line-height:1.5">{trigger_desc}</p>
              <div style="display:flex;gap:20px">
                <div>
                  <p style="font-size:11px;color:#555;margin:0 0 4px;
                             text-transform:uppercase;letter-spacing:1px">Price</p>
                  <p style="font-size:20px;font-weight:600;color:#f0f0f0;
                             margin:0">₹{current_price:,.2f}</p>
                </div>
                <div>
                  <p style="font-size:11px;color:#555;margin:0 0 4px;
                             text-transform:uppercase;letter-spacing:1px">Today</p>
                  <p style="font-size:20px;font-weight:600;
                             color:{chg_color};margin:0">
                    {chg_sign}{day_chg:.2f}%
                  </p>
                </div>
              </div>
            </div>
            <p style="font-size:12px;color:#333;margin:0">
              Sent by Voltr · your portfolio intelligence layer
            </p>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
        return True
    except:
        return False

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

def check_and_fire_alerts(alerts, alert_log):
    while True:
        for alert in alerts:
            if not alert.get("active"):
                continue
            try:
                hist = yf.Ticker(alert["ticker"]).history(period="1mo")
                if len(hist) < 2:
                    continue
                cp      = hist['Close'].iloc[-1]
                prev    = hist['Close'].iloc[-2]
                day_chg = ((cp - prev) / prev) * 100
                avg_vol = hist['Volume'].iloc[:-1].mean()
                cur_vol = hist['Volume'].iloc[-1]
                rsi_ser = compute_rsi(hist['Close'])
                cur_rsi = rsi_ser.iloc[-1] if not rsi_ser.empty else 50

                conditions_met = []
                pc = alert["price_cond"]
                pv = alert["price_val"]
                if pc == "Price rises above ₹" and cp > pv:
                    conditions_met.append(f"Price ₹{cp:,.2f} is above ₹{pv:,.2f}")
                elif pc == "Price drops below ₹" and cp < pv:
                    conditions_met.append(f"Price ₹{cp:,.2f} dropped below ₹{pv:,.2f}")
                elif pc == "Day change rises above %" and day_chg > pv:
                    conditions_met.append(f"Day change {day_chg:+.2f}% exceeded +{pv:.1f}%")
                elif pc == "Day change drops below %" and day_chg < -pv:
                    conditions_met.append(f"Day change {day_chg:+.2f}% dropped below -{pv:.1f}%")

                vc = alert["vol_cond"]
                if vc == "Volume is 2x average" and cur_vol > avg_vol * 2:
                    conditions_met.append(f"Volume {cur_vol:,.0f} is 2x the average")
                elif vc == "Volume is 3x average" and cur_vol > avg_vol * 3:
                    conditions_met.append(f"Volume {cur_vol:,.0f} is 3x the average")

                rc = alert["rsi_cond"]
                if rc == "RSI overbought (> 70)" and cur_rsi > 70:
                    conditions_met.append(f"RSI overbought at {cur_rsi:.1f}")
                elif rc == "RSI oversold (< 30)" and cur_rsi < 30:
                    conditions_met.append(f"RSI oversold at {cur_rsi:.1f}")

                total_conditions = sum([
                    1 for x in [alert["price_cond"], alert["vol_cond"], alert["rsi_cond"]]
                    if x != "-- None --"
                ])
                if len(conditions_met) == total_conditions and total_conditions > 0:
                    trigger_desc = " · ".join(conditions_met)
                    sent = send_alert_email(
                        alert["recipient"], alert["name"],
                        trigger_desc, cp, day_chg
                    )
                    if sent:
                        alert_log.append({
                            "stock":   alert["name"],
                            "trigger": trigger_desc,
                            "time":    datetime.now().strftime("%d %b %Y · %I:%M %p"),
                            "sent_to": alert["recipient"],
                        })
            except:
                continue
        time.sleep(60)

# ── start background thread once ─────────────────────────
if "bg_thread_started" not in st.session_state:
    st.session_state.bg_thread_started = True
    st.session_state.alerts            = []
    st.session_state.alert_log         = []
    t = threading.Thread(
        target=check_and_fire_alerts,
        args=(st.session_state.alerts, st.session_state.alert_log),
        daemon=True
    )
    t.start()

# ── page config ───────────────────────────────────────────
st.set_page_config(
    page_title="Voltr",
    page_icon="V",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebar"] {
    background: #0f0f0f;
    border-right: 1px solid #1e1e1e;
}
[data-testid="stSidebar"] * { color: #a0a0a0 !important; }
.stApp { background: #0a0a0a; }
.nw-metric {
    background: #141414;
    border: 1px solid #1e1e1e;
    border-radius: 12px;
    padding: 18px 20px;
}
.nw-metric-label {
    font-size: 11px; color: #555;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;
}
.nw-metric-value {
    font-size: 22px; font-weight: 600;
    color: #f0f0f0; letter-spacing: -0.5px;
}
.nw-metric-delta-up   { font-size: 12px; color: #4ade80; margin-top: 4px; }
.nw-metric-delta-down { font-size: 12px; color: #f87171; margin-top: 4px; }
.nw-signal {
    background: #141414; border: 1px solid #1e1e1e;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
}
.nw-signal-header {
    display: flex; justify-content: space-between;
    align-items: center; margin-bottom: 8px;
}
.nw-signal-name { font-size: 14px; font-weight: 600; color: #f0f0f0; }
.nw-badge-warn {
    background: #2a1f00; color: #f59e0b; font-size: 11px;
    padding: 3px 10px; border-radius: 20px; font-weight: 500;
}
.nw-badge-ok {
    background: #0f1f0f; color: #4ade80; font-size: 11px;
    padding: 3px 10px; border-radius: 20px; font-weight: 500;
}
.nw-verdict { font-size: 13px; color: #888; line-height: 1.6; margin-bottom: 10px; }
.nw-peer-row { display: flex; gap: 8px; flex-wrap: wrap; }
.nw-peer-chip {
    background: #1a1a1a; border: 1px solid #2a2a2a;
    border-radius: 6px; padding: 4px 10px; font-size: 11px; color: #888;
}
.nw-peer-chip b { color: #f0f0f0; }
.nw-news-item { padding: 10px 0; border-bottom: 1px solid #1e1e1e; font-size: 13px; }
.nw-news-item a { color: #a0a0a0; text-decoration: none; }
.nw-news-item a:hover { color: #f0f0f0; }
.nw-news-source { font-size: 11px; color: #444; margin-top: 3px; }
.nw-section {
    font-size: 11px; font-weight: 600; color: #555;
    text-transform: uppercase; letter-spacing: 0.8px; margin: 28px 0 14px;
}
</style>
""", unsafe_allow_html=True)

# ── constants ─────────────────────────────────────────────
NEWS_API_KEY = "2eef45892af14f5b91ea0338619e3d39"

POPULAR_STOCKS = {
    "Reliance Industries": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "ITC": "ITC.NS",
    "Kotak Mahindra Bank": "KOTAKBANK.NS",
    "Larsen & Toubro": "LT.NS",
    "Axis Bank": "AXISBANK.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Asian Paints": "ASIANPAINT.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Wipro": "WIPRO.NS",
    "HCL Technologies": "HCLTECH.NS",
    "Titan Company": "TITAN.NS",
    "Zomato": "ZOMATO.NS",
    "Paytm": "ONE97.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "ONGC": "ONGC.NS",
    "Coal India": "COALINDIA.NS",
    "BPCL": "BPCL.NS",
    "IOC": "IOC.NS",
    "Vedanta": "VEDL.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Hindalco": "HINDALCO.NS",
    "Bajaj Auto": "BAJAJ-AUTO.NS",
    "Hero MotoCorp": "HEROMOTOCO.NS",
    "Nykaa": "NYKAA.NS",
    "Dmart": "DMART.NS",
    "Pidilite": "PIDILITIND.NS",
    "Havells": "HAVELLS.NS",
    "Berger Paints": "BERGEPAINT.NS",
}

SECTOR_PEERS = {
    "RELIANCE.NS":   ["ONGC.NS", "IOC.NS", "BPCL.NS"],
    "TCS.NS":        ["INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "HDFCBANK.NS":   ["ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "INFY.NS":       ["TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "ICICIBANK.NS":  ["HDFCBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "HINDUNILVR.NS": ["ITC.NS", "NESTLEIND.NS", "ASIANPAINT.NS"],
    "ITC.NS":        ["HINDUNILVR.NS", "NESTLEIND.NS", "TITAN.NS"],
    "KOTAKBANK.NS":  ["HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS"],
    "LT.NS":         ["NTPC.NS", "TATAMOTORS.NS", "MARUTI.NS"],
    "AXISBANK.NS":   ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS"],
    "BAJFINANCE.NS": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS"],
    "ASIANPAINT.NS": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS"],
    "MARUTI.NS":     ["TATAMOTORS.NS", "LT.NS", "BAJFINANCE.NS"],
    "SUNPHARMA.NS":  ["WIPRO.NS", "HCLTECH.NS", "INFY.NS"],
    "WIPRO.NS":      ["TCS.NS", "INFY.NS", "HCLTECH.NS"],
    "HCLTECH.NS":    ["TCS.NS", "INFY.NS", "WIPRO.NS"],
    "TITAN.NS":      ["HINDUNILVR.NS", "ITC.NS", "ASIANPAINT.NS"],
    "NESTLEIND.NS":  ["HINDUNILVR.NS", "ITC.NS", "ASIANPAINT.NS"],
    "TATAMOTORS.NS": ["MARUTI.NS", "LT.NS", "BAJFINANCE.NS"],
    "NTPC.NS":       ["LT.NS", "RELIANCE.NS", "ONGC.NS"],
    "ZOMATO.NS":     ["ONE97.NS", "NYKAA.NS", "DMART.NS"],
    "ONE97.NS":      ["ZOMATO.NS", "NYKAA.NS", "BAJFINANCE.NS"],
    "NYKAA.NS":      ["ZOMATO.NS", "ONE97.NS", "DMART.NS"],
    "TATASTEEL.NS":  ["JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS"],
    "JSWSTEEL.NS":   ["TATASTEEL.NS", "HINDALCO.NS", "VEDL.NS"],
    "HINDALCO.NS":   ["TATASTEEL.NS", "JSWSTEEL.NS", "VEDL.NS"],
    "VEDL.NS":       ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS"],
    "ONGC.NS":       ["RELIANCE.NS", "IOC.NS", "BPCL.NS"],
    "IOC.NS":        ["RELIANCE.NS", "ONGC.NS", "BPCL.NS"],
    "BPCL.NS":       ["RELIANCE.NS", "ONGC.NS", "IOC.NS"],
    "COALINDIA.NS":  ["NTPC.NS", "ONGC.NS", "RELIANCE.NS"],
    "DMART.NS":      ["ZOMATO.NS", "NYKAA.NS", "HINDUNILVR.NS"],
    "PIDILITIND.NS": ["ASIANPAINT.NS", "BERGEPAINT.NS", "HINDUNILVR.NS"],
    "HAVELLS.NS":    ["LT.NS", "BERGEPAINT.NS", "PIDILITIND.NS"],
    "BERGEPAINT.NS": ["ASIANPAINT.NS", "PIDILITIND.NS", "HINDUNILVR.NS"],
    "BAJAJ-AUTO.NS": ["HEROMOTOCO.NS", "MARUTI.NS", "TATAMOTORS.NS"],
    "HEROMOTOCO.NS": ["BAJAJ-AUTO.NS", "MARUTI.NS", "TATAMOTORS.NS"],
    "ADANIPORTS.NS": ["LT.NS", "NTPC.NS", "RELIANCE.NS"],
}

# ════════════════════════════════════════════════════════════
# FUNCTIONS
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def search_stocks(query):
    if not query or len(query) < 2:
        return POPULAR_STOCKS
    
    # first check popular stocks for instant matches
    query_lower = query.lower()
    quick_matches = {
        k: v for k, v in POPULAR_STOCKS.items()
        if query_lower in k.lower()
    }
    if quick_matches:
        return quick_matches
    
   # fallback to yfinance search
    try:
        results = yf.Search(query, news_count=0, max_results=10)
        quotes  = results.quotes
        matches = {}
        for q in quotes:
            symbol = q.get("symbol", "")
            name   = q.get("longname") or q.get("shortname") or symbol
            if symbol.endswith(".NS") or symbol.endswith(".BO"):
                matches[f"{name} ({symbol})"] = symbol
        return matches if matches else POPULAR_STOCKS
    except:
        return POPULAR_STOCKS

@st.cache_data(ttl=300)
def load_history(ticker, period):
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome")
        return yf.Ticker(ticker, session=session).history(period=period)
    except Exception:
        try:
            return yf.Ticker(ticker).history(period=period)
        except Exception:
            return pd.DataFrame()

@st.cache_data(ttl=300)
def get_current_price(ticker):
    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate="chrome")
        hist = yf.Ticker(ticker, session=session).history(period="2d")
        return hist['Close'].iloc[-1] if not hist.empty else None
    except Exception:
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            return hist['Close'].iloc[-1] if not hist.empty else None
        except Exception:
            return None

@st.cache_data(ttl=600)
def get_news(company_name):
    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={company_name}+stock+India&"
        f"language=en&sortBy=publishedAt&pageSize=5&"
        f"apiKey={NEWS_API_KEY}"
    )
    try:
        r    = requests.get(url, timeout=5)
        data = r.json()
        if data.get("status") == "ok":
            return data.get("articles", [])
    except:
        pass
    return []

@st.cache_data(ttl=300)
def get_peer_moves(peer_tickers):
    moves = {}
    for ticker in peer_tickers:
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                chg = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2])
                       / hist['Close'].iloc[-2]) * 100
                moves[ticker] = round(chg, 2)
        except:
            moves[ticker] = None
    return moves

def analyze_move(ticker, day_change_pct):
    peers      = SECTOR_PEERS.get(ticker, [])
    peer_moves = get_peer_moves(tuple(peers)) if peers else {}
    valid      = [v for v in peer_moves.values() if v is not None]
    avg_peer   = round(sum(valid) / len(valid), 2) if valid else 0
    same_dir   = (day_change_pct > 0 and avg_peer > 0) or \
                 (day_change_pct < 0 and avg_peer < 0)
    if same_dir and abs(avg_peer) > 0.5:
        verdict     = "market-wide"
        explanation = (
            f"Sector peers also averaged {avg_peer:+.2f}% today. "
            f"This looks like a broad sector or market move — not specific to this stock."
        )
    else:
        verdict     = "company-specific"
        explanation = (
            f"Sector peers moved only {avg_peer:+.2f}% on average while this stock moved "
            f"{day_change_pct:+.2f}%. This appears company-specific — check recent news below."
        ) if peers else (
            f"No peer data available. This stock moved {day_change_pct:+.2f}% today."
        )
    return verdict, explanation, peer_moves

@st.cache_data(ttl=3600)
def get_beta(ticker):
    try:
        stock_hist = yf.Ticker(ticker).history(period="1y")
        nifty_hist = yf.Ticker("^NSEI").history(period="1y")
        if stock_hist.empty or nifty_hist.empty:
            return 1.0
        stock_ret = stock_hist['Close'].pct_change().dropna()
        nifty_ret = nifty_hist['Close'].pct_change().dropna()
        combined  = pd.DataFrame({"stock": stock_ret, "nifty": nifty_ret}).dropna()
        if len(combined) < 30:
            return 1.0
        cov  = combined['stock'].cov(combined['nifty'])
        var  = combined['nifty'].var()
        return round(cov / var, 2) if var != 0 else 1.0
    except:
        return 1.0

@st.cache_data(ttl=3600)
def get_nifty_return():
    try:
        nifty = yf.Ticker("^NSEI").history(period="1mo")
        if len(nifty) >= 2:
            start = nifty['Close'].iloc[0]
            end   = nifty['Close'].iloc[-1]
            return ((end - start) / start) * 100
    except:
        pass
    return 0.0

# ════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Voltr")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["My Portfolio", "Stock Explorer", "Stress Tester",
         "Behavior Detector", "Sector Heatmap", "Alerts",
         "Report Card", "Market Signals"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("Live NSE & BSE data")
    st.caption("Signal over noise")

# ════════════════════════════════════════════════════════════
# PAGE: MY PORTFOLIO
# ════════════════════════════════════════════════════════════

if page == "My Portfolio":

    st.markdown("## My Portfolio")
    st.caption("Portfolio intelligence. No noise.")

    if "holdings" not in st.session_state:
        st.session_state.holdings = []

    with st.expander("+ Add a holding",
                     expanded=len(st.session_state.holdings) == 0):
        st.caption("Search any NSE or BSE listed company")
        search_query = st.text_input(
            "Search company name",
            placeholder="e.g. Zomato, HDFC, Tata Steel...",
            key="stock_search"
        )
        search_results = search_stocks(search_query)
        if search_results:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                stock_display       = st.selectbox("Select stock",
                    list(search_results.keys()), key="stock_select")
                selected_ticker_add = search_results[stock_display]
                st.caption(f"Ticker: `{selected_ticker_add}`")
            with c2:
                quantity  = st.number_input("Quantity", min_value=1, value=10, step=1)
            with c3:
                buy_price = st.number_input("Avg buy price (₹)",
                    min_value=1.0, value=100.0, step=0.5)
            with c4:
                st.write("")
                st.write("")
                if st.button("Add", use_container_width=True):
                    clean_name = stock_display.split(" (")[0]
                    st.session_state.holdings.append({
                        "Stock": clean_name, "Ticker": selected_ticker_add,
                        "Qty": quantity, "Buy Price": buy_price,
                    })
                    st.rerun()
        else:
            st.warning("No results found. Try a different search term.")

    if st.session_state.holdings:
        rows           = []
        total_invested = 0
        total_current  = 0
        today_pnl      = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Ticker"])
            if cp:
                hist2    = load_history(h["Ticker"], "2d")
                prev_p   = hist2['Close'].iloc[-2] if len(hist2) >= 2 else cp
                day_chg  = ((cp - prev_p) / prev_p) * 100
                invested = h["Qty"] * h["Buy Price"]
                cur_val  = h["Qty"] * cp
                pnl      = cur_val - invested
                pnl_pct  = (pnl / invested) * 100
                today_mv = h["Qty"] * (cp - prev_p)
                rows.append({
                    "stock": h["Stock"], "ticker": h["Ticker"],
                    "qty": h["Qty"], "buy_price": h["Buy Price"],
                    "cur_price": cp, "invested": invested,
                    "cur_val": cur_val, "pnl": pnl,
                    "pnl_pct": pnl_pct, "day_chg": day_chg,
                    "today_move": today_mv,
                })
                total_invested += invested
                total_current  += cur_val
                today_pnl      += today_mv

        total_pnl     = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
        today_pct     = (today_pnl / (total_current - today_pnl) * 100) \
                        if (total_current - today_pnl) else 0

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Invested</div>
              <div class="nw-metric-value">₹{total_invested:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">₹{total_current:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            dc = "nw-metric-delta-up" if total_pnl >= 0 else "nw-metric-delta-down"
            sg = "+" if total_pnl >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Total P&L</div>
              <div class="nw-metric-value">₹{sg}{total_pnl:,.0f}</div>
              <div class="{dc}">{sg}{total_pnl_pct:.2f}% all time</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            tc = "nw-metric-delta-up" if today_pnl >= 0 else "nw-metric-delta-down"
            ts = "+" if today_pnl >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Today</div>
              <div class="nw-metric-value">₹{ts}{today_pnl:,.0f}</div>
              <div class="{tc}">{ts}{today_pct:.2f}% today</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Holdings</div>", unsafe_allow_html=True)
        for r in rows:
            pc = "#4ade80" if r["pnl"] >= 0 else "#f87171"
            dc = "#4ade80" if r["day_chg"] >= 0 else "#f87171"
            ps = "+" if r["pnl"] >= 0 else ""
            ds = "+" if r["day_chg"] >= 0 else ""
            c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 2, 2, 2, 2])
            c1.markdown(f"**{r['stock']}**")
            c2.markdown(f"<span style='color:#555'>{r['qty']} sh</span>", unsafe_allow_html=True)
            c3.markdown(f"<span style='color:#888'>₹{r['buy_price']:,.2f}</span>", unsafe_allow_html=True)
            c4.markdown(f"₹{r['cur_price']:,.2f}")
            c5.markdown(f"<span style='color:{pc}'>{ps}₹{r['pnl']:,.0f} ({ps}{r['pnl_pct']:.1f}%)</span>", unsafe_allow_html=True)
            c6.markdown(f"<span style='color:{dc}'>{ds}{r['day_chg']:.2f}% today</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Allocation</div>", unsafe_allow_html=True)
        alloc_df = pd.DataFrame([{"Stock": r["stock"], "Value": r["cur_val"]} for r in rows])
        fig_pie  = px.pie(alloc_df, values="Value", names="Stock", hole=0.5,
            color_discrete_sequence=["#a78bfa","#34d399","#60a5fa","#f472b6",
                                      "#fbbf24","#f87171","#38bdf8","#fb923c","#a3e635"])
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0,r=0,t=10,b=0), legend=dict(font=dict(color="#888",size=12)), height=300)
        fig_pie.update_traces(textfont_color="#f0f0f0")
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("<div class='nw-section'>Market signals today</div>", unsafe_allow_html=True)
        for r in rows:
            verdict, explanation, peer_moves = analyze_move(r["ticker"], r["day_chg"])
            badge = ("nw-badge-warn", "Company-specific") if verdict == "company-specific" \
                    else ("nw-badge-ok", "Market-wide")
            dc    = "#4ade80" if r["day_chg"] >= 0 else "#f87171"
            ds    = "+" if r["day_chg"] >= 0 else ""
            peers_html = ""
            for pticker, pmove in peer_moves.items():
                label = pticker.replace(".NS","").replace(".BO","")
                val   = f"{pmove:+.2f}%" if pmove is not None else "N/A"
                pc    = "#4ade80" if (pmove or 0) >= 0 else "#f87171"
                peers_html += f'<div class="nw-peer-chip">{label} <b style="color:{pc}">{val}</b></div>'
            articles  = get_news(r["stock"])
            news_html = ""
            for a in articles[:3]:
                title  = a.get("title","")[:90]
                url    = a.get("url","#")
                source = a.get("source",{}).get("name","")
                pub    = a.get("publishedAt","")[:10]
                news_html += f"""<div class="nw-news-item">
                  <a href="{url}" target="_blank">{title}</a>
                  <div class="nw-news-source">{source} &middot; {pub}</div>
                </div>"""
            st.markdown(f"""<div class="nw-signal">
              <div class="nw-signal-header">
                <span class="nw-signal-name">{r['stock']}
                  <span style="color:{dc};font-weight:400;margin-left:6px">{ds}{r['day_chg']:.2f}%</span>
                </span>
                <span class="{badge[0]}">{badge[1]}</span>
              </div>
              <div class="nw-verdict">{explanation}</div>
              <div class="nw-peer-row">{peers_html}</div>
              {f'<div style="margin-top:12px">{news_html}</div>' if news_html else ''}
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear portfolio"):
            st.session_state.holdings = []
            st.rerun()
    else:
        st.info("No holdings yet — use the form above to add your first stock.")

# ════════════════════════════════════════════════════════════
# PAGE: STOCK EXPLORER
# ════════════════════════════════════════════════════════════

elif page == "Stock Explorer":

    st.markdown("## Stock Explorer")
    st.caption("Candlestick charts and key stats for any NSE or BSE listed stock")

    search_query_ex  = st.sidebar.text_input("Search company",
        placeholder="e.g. Infosys, Zomato...", key="explorer_search")
    explorer_results = search_stocks(search_query_ex)
    selected_display = st.sidebar.selectbox("Select", list(explorer_results.keys()))
    selected_ticker  = explorer_results[selected_display]
    selected_name    = selected_display.split(" (")[0]
    period           = st.sidebar.selectbox("Period", ["1mo","3mo","6mo","1y"], index=1)

    hist = load_history(selected_ticker, period)
    if not hist.empty:
        latest = hist['Close'].iloc[-1]
        prev   = hist['Close'].iloc[-2]
        chg    = ((latest - prev) / prev) * 100
        sign   = "+" if chg >= 0 else ""
        cc     = "nw-metric-delta-up" if chg >= 0 else "nw-metric-delta-down"
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Price</div>
              <div class="nw-metric-value">₹{latest:,.2f}</div>
              <div class="{cc}">{sign}{chg:.2f}% today</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">52W High</div>
              <div class="nw-metric-value">₹{hist['High'].max():,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">52W Low</div>
              <div class="nw-metric-value">₹{hist['Low'].min():,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Avg volume</div>
              <div class="nw-metric-value">{hist['Volume'].mean():,.0f}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Price chart</div>", unsafe_allow_html=True)
        fig = go.Figure(data=[go.Candlestick(
            x=hist.index, open=hist['Open'], high=hist['High'],
            low=hist['Low'], close=hist['Close'],
            increasing_line_color='#4ade80', decreasing_line_color='#f87171',
            name=selected_name
        )])
        fig.update_layout(xaxis_rangeslider_visible=False, plot_bgcolor='#0a0a0a',
            paper_bgcolor='rgba(0,0,0,0)', height=460,
            margin=dict(l=0,r=0,t=10,b=0),
            xaxis=dict(showgrid=False, color="#444"),
            yaxis=dict(showgrid=True, gridcolor='#1a1a1a', color="#444", title="Price (₹)"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Could not fetch data. Check your connection.")

# ════════════════════════════════════════════════════════════
# PAGE: STRESS TESTER
# ════════════════════════════════════════════════════════════

elif page == "Stress Tester":

    st.markdown("## Stress Tester")
    st.caption("See how your portfolio holds up under market shocks")

    if not st.session_state.get("holdings"):
        st.info("Add stocks to your portfolio first, then come back here.")
    else:
        SCENARIOS = {
            "Nifty crashes 10%":             -10.0,
            "Nifty crashes 15%":             -15.0,
            "Nifty crashes 20% (2008-like)": -20.0,
            "Nifty rallies 10%":             +10.0,
            "RBI rate hike (mild -3%)":      -3.0,
            "RBI rate hike (aggressive -7%)": -7.0,
            "Global selloff -12%":           -12.0,
            "Custom scenario":               None,
        }
        st.markdown("<div class='nw-section'>Choose a scenario</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_scenario = st.selectbox("Scenario", list(SCENARIOS.keys()),
                label_visibility="collapsed")
        with col2:
            if SCENARIOS[selected_scenario] is None:
                market_move = st.number_input("Market move (%)", value=-10.0,
                    min_value=-50.0, max_value=50.0, step=0.5)
            else:
                market_move = SCENARIOS[selected_scenario]
                col = '#f87171' if market_move < 0 else '#4ade80'
                st.markdown(f"""<div class="nw-metric" style="padding:12px 16px">
                  <div class="nw-metric-label">Market move</div>
                  <div class="nw-metric-value" style="font-size:18px;color:{col}">
                    {market_move:+.1f}%
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Portfolio impact</div>", unsafe_allow_html=True)
        st.caption("Each stock is re-priced using its 1-year beta vs Nifty 50")

        stress_rows    = []
        total_current  = 0
        total_stressed = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Ticker"])
            if not cp:
                continue
            beta           = get_beta(h["Ticker"])
            stock_move     = market_move * beta
            stressed_price = cp * (1 + stock_move / 100)
            cur_val        = h["Qty"] * cp
            stressed_val   = h["Qty"] * stressed_price
            impact         = stressed_val - cur_val
            impact_pct     = (impact / cur_val) * 100
            stress_rows.append({
                "stock": h["Stock"], "beta": beta,
                "cur_price": cp, "stressed_price": stressed_price,
                "cur_val": cur_val, "stressed_val": stressed_val,
                "impact": impact, "impact_pct": impact_pct,
            })
            total_current  += cur_val
            total_stressed += stressed_val

        total_impact     = total_stressed - total_current
        total_impact_pct = (total_impact / total_current * 100) if total_current else 0

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">₹{total_current:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Stressed value</div>
              <div class="nw-metric-value">₹{total_stressed:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            ic  = "nw-metric-delta-up" if total_impact >= 0 else "nw-metric-delta-down"
            is_ = "+" if total_impact >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Estimated impact</div>
              <div class="nw-metric-value">₹{is_}{total_impact:,.0f}</div>
              <div class="{ic}">{is_}{total_impact_pct:.2f}% portfolio</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        stress_rows.sort(key=lambda x: x["impact"])
        for r in stress_rows:
            ic  = "#4ade80" if r["impact"] >= 0 else "#f87171"
            is_ = "+" if r["impact"] >= 0 else ""
            bc  = "#4ade80" if r["beta"] < 1 else "#f59e0b" if r["beta"] < 1.5 else "#f87171"
            bl  = "Low risk" if r["beta"] < 1 else "Medium risk" if r["beta"] < 1.5 else "High risk"
            c1, c2, c3, c4, c5 = st.columns([3, 1, 2, 2, 2])
            c1.markdown(f"**{r['stock']}**")
            c2.markdown(f"<span style='color:{bc};font-size:12px'>Beta {r['beta']}<br>{bl}</span>", unsafe_allow_html=True)
            c3.markdown(f"<span style='color:#888'>Now ₹{r['cur_price']:,.2f}</span>", unsafe_allow_html=True)
            c4.markdown(f"<span style='color:{ic}'>Stressed ₹{r['stressed_price']:,.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span style='color:{ic}'>{is_}₹{r['impact']:,.0f} ({is_}{r['impact_pct']:.1f}%)</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>How beta works</div>", unsafe_allow_html=True)
        st.markdown("""
- **Beta < 1** — moves less than the market (defensive)
- **Beta = 1** — moves in line with the market
- **Beta > 1** — moves more than the market (aggressive)

Betas are calculated using 1 year of daily returns vs the Nifty 50 index.
        """)

# ════════════════════════════════════════════════════════════
# PAGE: BEHAVIOR DETECTOR
# ════════════════════════════════════════════════════════════

elif page == "Behavior Detector":

    st.markdown("## Behavior Detector")
    st.caption("Log your trades and discover what your patterns reveal about you")

    if "trade_log" not in st.session_state:
        st.session_state.trade_log = []

    with st.expander("+ Log a trade", expanded=len(st.session_state.trade_log) == 0):
        st.caption("Record every buy or sell to build your behavioral profile")
        tl1, tl2, tl3, tl4, tl5 = st.columns([3, 1, 2, 2, 1])
        with tl1:
            t_search  = st.text_input("Search stock",
                placeholder="e.g. Infosys, Zomato...", key="trade_search")
            t_results = search_stocks(t_search)
            t_display = st.selectbox("Stock", list(t_results.keys()), key="trade_stock")
            t_ticker  = t_results[t_display]
            t_name    = t_display.split(" (")[0]
        with tl2:
            t_action = st.selectbox("Action", ["Buy", "Sell"], key="trade_action")
        with tl3:
            t_price = st.number_input("Price (₹)", min_value=0.1,
                value=100.0, step=0.5, key="trade_price")
        with tl4:
            t_date = st.date_input("Date", key="trade_date")
        with tl5:
            st.write("")
            st.write("")
            if st.button("Log", use_container_width=True):
                try:
                    nifty_prev = yf.Ticker("^NSEI").history(
                        start=str(t_date - pd.Timedelta(days=5)),
                        end=str(t_date))
                    nifty_3d = ((nifty_prev['Close'].iloc[-1] -
                                 nifty_prev['Close'].iloc[-3]) /
                                nifty_prev['Close'].iloc[-3]) * 100 \
                               if len(nifty_prev) >= 3 else 0.0
                except:
                    nifty_3d = 0.0
                st.session_state.trade_log.append({
                    "stock": t_name, "ticker": t_ticker,
                    "action": t_action, "price": t_price,
                    "date": str(t_date), "nifty_3d": round(nifty_3d, 2),
                })
                st.success(f"Logged {t_action} — {t_name} at ₹{t_price:.2f}")
                st.rerun()

    if st.session_state.trade_log:
        st.markdown("<div class='nw-section'>Trade history</div>", unsafe_allow_html=True)
        for t in st.session_state.trade_log:
            ac = "#4ade80" if t["action"] == "Buy" else "#f87171"
            c1, c2, c3, c4 = st.columns([3, 1, 2, 2])
            c1.markdown(f"**{t['stock']}**")
            c2.markdown(f"<span style='color:{ac}'>{t['action']}</span>", unsafe_allow_html=True)
            c3.markdown(f"₹{t['price']:,.2f}")
            c4.markdown(f"<span style='color:#555'>{t['date']}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Behavioral analysis</div>", unsafe_allow_html=True)
        trades_df = pd.DataFrame(st.session_state.trade_log)
        buys      = trades_df[trades_df["action"] == "Buy"]
        sells     = trades_df[trades_df["action"] == "Sell"]

        if len(buys) >= 2:
            fomo_buys = buys[buys["nifty_3d"] > 2.0]
            fomo_pct  = len(fomo_buys) / len(buys) * 100
            fc        = "#f87171" if fomo_pct > 50 else "#f59e0b" if fomo_pct > 25 else "#4ade80"
            fv        = ("Strong FOMO pattern. Most buys follow 2%+ market rallies — "
                         "you may be chasing momentum.") if fomo_pct > 50 else \
                        ("Mild FOMO tendency. Some buys follow rallies.") if fomo_pct > 25 else \
                        ("No significant FOMO pattern detected.")
            st.markdown(f"""<div class="nw-signal">
              <div class="nw-signal-header">
                <span class="nw-signal-name">FOMO detector</span>
                <span style="color:{fc};font-size:13px;font-weight:600">{fomo_pct:.0f}% of buys after rallies</span>
              </div>
              <div class="nw-verdict">{fv}</div>
            </div>""", unsafe_allow_html=True)

        if len(trades_df) >= 3:
            trades_df["date_parsed"] = pd.to_datetime(trades_df["date"])
            date_range = (trades_df["date_parsed"].max() - trades_df["date_parsed"].min()).days
            if date_range > 0:
                tpm = len(trades_df) / (date_range / 30)
                oc  = "#f87171" if tpm > 10 else "#f59e0b" if tpm > 5 else "#4ade80"
                ov  = (f"High frequency — {tpm:.1f} trades/month. Frequent trading "
                       f"typically hurts retail returns.") if tpm > 10 else \
                      (f"Moderate frequency — {tpm:.1f} trades/month.") if tpm > 5 else \
                      (f"Patient style — {tpm:.1f} trades/month. Research favours this.")
                st.markdown(f"""<div class="nw-signal">
                  <div class="nw-signal-header">
                    <span class="nw-signal-name">Trading frequency</span>
                    <span style="color:{oc};font-size:13px;font-weight:600">{tpm:.1f} trades / month</span>
                  </div>
                  <div class="nw-verdict">{ov}</div>
                </div>""", unsafe_allow_html=True)

        if len(buys) >= 2:
            sc    = buys["stock"].value_counts()
            tp    = sc.iloc[0] / len(buys) * 100
            cc    = "#f87171" if tp > 40 else "#4ade80"
            cv    = (f"{tp:.0f}% of trades in {sc.index[0]} — heavy concentration.") if tp > 40 else \
                    ("Trades spread across multiple stocks — good diversification.")
            st.markdown(f"""<div class="nw-signal">
              <div class="nw-signal-header">
                <span class="nw-signal-name">Concentration check</span>
                <span style="color:{cc};font-size:13px;font-weight:600">{tp:.0f}% in {sc.index[0]}</span>
              </div>
              <div class="nw-verdict">{cv}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear trade log"):
            st.session_state.trade_log = []
            st.rerun()
    else:
        st.info("Log at least 3 trades to unlock your behavioral analysis.")

# ════════════════════════════════════════════════════════════
# PAGE: SECTOR HEATMAP
# ════════════════════════════════════════════════════════════

elif page == "Sector Heatmap":

    st.markdown("## Sector Rotation Heatmap")
    st.caption("Which sectors are gaining and losing momentum — updated daily")

    SECTORS = {
        "Banking":        ["HDFCBANK.NS","ICICIBANK.NS","KOTAKBANK.NS","AXISBANK.NS"],
        "IT":             ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS"],
        "Energy":         ["RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS"],
        "FMCG":           ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS","DABUR.NS"],
        "Auto":           ["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS","HEROMOTOCO.NS"],
        "Pharma":         ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS"],
        "Metals":         ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","VEDL.NS"],
        "Infrastructure": ["LT.NS","NTPC.NS","ADANIPORTS.NS","COALINDIA.NS"],
        "Consumer Tech":  ["ZOMATO.NS","ONE97.NS","NYKAA.NS","DMART.NS"],
        "Real Estate":    ["DLF.NS","GODREJPROP.NS","OBEROIRLTY.NS","PRESTIGE.NS"],
    }

    @st.cache_data(ttl=3600)
    def get_sector_returns():
        results = {}
        for sector, tickers in SECTORS.items():
            s1d, s1w, s1mo = [], [], []
            for ticker in tickers:
                try:
                    hist = yf.Ticker(ticker).history(period="2mo")
                    if len(hist) < 5:
                        continue
                    pn = hist['Close'].iloc[-1]
                    s1d.append( ((pn - hist['Close'].iloc[-2])  / hist['Close'].iloc[-2])  * 100)
                    s1w.append( ((pn - hist['Close'].iloc[-6])  / hist['Close'].iloc[-6])  * 100 if len(hist)>=6  else 0)
                    s1mo.append(((pn - hist['Close'].iloc[-22]) / hist['Close'].iloc[-22]) * 100 if len(hist)>=22 else 0)
                except:
                    continue
            if s1d:
                results[sector] = {
                    "1d":  round(sum(s1d)/len(s1d),   2),
                    "1w":  round(sum(s1w)/len(s1w),   2),
                    "1mo": round(sum(s1mo)/len(s1mo), 2),
                }
        return results

    with st.spinner("Fetching sector data..."):
        sector_data = get_sector_returns()

    if not sector_data:
        st.error("Could not fetch sector data.")
    else:
        timeframe = st.segmented_control("Timeframe",
            ["Today", "This week", "This month"], default="This week")
        tf_key = {"Today": "1d", "This week": "1w", "This month": "1mo"}[timeframe]

        st.markdown("<div class='nw-section'>Sector performance</div>", unsafe_allow_html=True)
        sorted_sectors = sorted(sector_data.items(), key=lambda x: x[1][tf_key], reverse=True)
        all_returns    = [abs(v[tf_key]) for _, v in sorted_sectors]
        max_abs        = max(all_returns) if all_returns else 1

        cols = st.columns(2)
        for i, (sector, returns) in enumerate(sorted_sectors):
            ret       = returns[tf_key]
            sign      = "+" if ret >= 0 else ""
            intensity = min(abs(ret) / max_abs, 1.0)
            if ret >= 0:
                g = int(150 + 105 * intensity)
                r = int(20 + 20 * (1 - intensity))
                b = int(20 + 20 * (1 - intensity))
            else:
                r = int(150 + 105 * intensity)
                g = int(20 + 20 * (1 - intensity))
                b = int(20 + 20 * (1 - intensity))
            bg   = f"rgb({r},{g},{b})"
            tc   = "#0a0a0a" if intensity > 0.5 else "#f0f0f0"
            r1d  = returns["1d"]
            r1w  = returns["1w"]
            r1mo = returns["1mo"]
            with cols[i % 2]:
                st.markdown(f"""<div style="background:{bg};border-radius:12px;
                    padding:18px 20px;margin-bottom:10px">
                  <div style="font-size:13px;font-weight:600;color:{tc};margin-bottom:6px">{sector}</div>
                  <div style="font-size:28px;font-weight:700;color:{tc};letter-spacing:-1px;margin-bottom:10px">
                    {sign}{ret:.2f}%</div>
                  <div style="display:flex;gap:12px;font-size:11px;color:{tc};opacity:0.75">
                    <span>1D {'+' if r1d>=0 else ''}{r1d:.2f}%</span>
                    <span>1W {'+' if r1w>=0 else ''}{r1w:.2f}%</span>
                    <span>1M {'+' if r1mo>=0 else ''}{r1mo:.2f}%</span>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Comparison chart</div>", unsafe_allow_html=True)
        chart_df = pd.DataFrame([{"Sector": s, "Return (%)": v[tf_key]} for s, v in sorted_sectors])
        colors_bar = ["#4ade80" if r >= 0 else "#f87171" for r in chart_df["Return (%)"]]
        fig_bar = go.Figure(go.Bar(
            x=chart_df["Return (%)"], y=chart_df["Sector"], orientation="h",
            marker_color=colors_bar,
            text=[f"{'+' if r>=0 else ''}{r:.2f}%" for r in chart_df["Return (%)"]],
            textposition="outside", textfont=dict(color="#888", size=12),
        ))
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            height=420, margin=dict(l=0,r=60,t=10,b=0),
            xaxis=dict(showgrid=True, gridcolor='#1a1a1a', color="#444",
                       zeroline=True, zerolinecolor="#333"),
            yaxis=dict(showgrid=False, color="#888"))
        st.plotly_chart(fig_bar, use_container_width=True)

        top    = sorted_sectors[0]
        bottom = sorted_sectors[-1]
        st.markdown("<div class='nw-section'>Reading the heatmap</div>", unsafe_allow_html=True)
        st.markdown(f"""
**Strongest:** {top[0]} ({'+' if top[1][tf_key]>=0 else ''}{top[1][tf_key]:.2f}%) — money rotating in.

**Weakest:** {bottom[0]} ({'+' if bottom[1][tf_key]>=0 else ''}{bottom[1][tf_key]:.2f}%) — institutional selling likely.
        """)

# ════════════════════════════════════════════════════════════
# PAGE: ALERTS
# ════════════════════════════════════════════════════════════

elif page == "Alerts":

    st.markdown("## Smart Alerts")
    st.caption("Set compound conditions — get emailed when they trigger")

    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "alert_log" not in st.session_state:
        st.session_state.alert_log = []

    st.markdown("<div class='nw-section'>Create an alert</div>", unsafe_allow_html=True)
    with st.expander("+ New alert", expanded=len(st.session_state.alerts) == 0):
        ac1, ac2 = st.columns(2)
        with ac1:
            alert_search  = st.text_input("Search stock",
                placeholder="e.g. Zomato, Infosys...", key="alert_search")
            alert_results = search_stocks(alert_search)
            alert_display = st.selectbox("Stock", list(alert_results.keys()), key="alert_stock")
            alert_ticker  = alert_results[alert_display]
            alert_name    = alert_display.split(" (")[0]
        with ac2:
            recipient_email = st.text_input("Send alert to",
                placeholder="you@gmail.com", key="alert_email")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Condition 1 — Price**")
        p1, p2 = st.columns(2)
        with p1:
            price_condition = st.selectbox("Price trigger",
                ["-- None --","Price rises above ₹","Price drops below ₹",
                 "Day change rises above %","Day change drops below %"],
                key="price_cond")
        with p2:
            price_value = st.number_input("Value", min_value=0.0,
                value=500.0, step=0.5, key="price_val")

        st.markdown("**Condition 2 — Volume (optional)**")
        volume_condition = st.selectbox("Volume trigger",
            ["-- None --","Volume is 2x average","Volume is 3x average"], key="vol_cond")

        st.markdown("**Condition 3 — RSI (optional)**")
        rsi_condition = st.selectbox("RSI signal",
            ["-- None --","RSI overbought (> 70)","RSI oversold (< 30)"], key="rsi_cond")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create alert", use_container_width=True):
            if not recipient_email:
                st.warning("Enter a recipient email address.")
            elif price_condition == "-- None --" and \
                 volume_condition == "-- None --" and \
                 rsi_condition    == "-- None --":
                st.warning("Set at least one condition.")
            else:
                st.session_state.alerts.append({
                    "name": alert_name, "ticker": alert_ticker,
                    "recipient": recipient_email,
                    "price_cond": price_condition, "price_val": price_value,
                    "vol_cond": volume_condition, "rsi_cond": rsi_condition,
                    "active": True,
                    "created": datetime.now().strftime("%d %b %Y"),
                })
                st.success(f"Alert created for {alert_name}")
                st.rerun()

    if st.session_state.alerts:
        st.markdown("<div class='nw-section'>Active alerts</div>", unsafe_allow_html=True)
        for i, alert in enumerate(st.session_state.alerts):
            if not alert["active"]:
                continue
            conditions = []
            if alert["price_cond"] != "-- None --":
                conditions.append(f"{alert['price_cond']} {alert['price_val']}")
            if alert["vol_cond"] != "-- None --":
                conditions.append(alert["vol_cond"])
            if alert["rsi_cond"] != "-- None --":
                conditions.append(alert["rsi_cond"])
            cond_str = " AND ".join(conditions)
            c1, c2, c3 = st.columns([3, 4, 1])
            c1.markdown(f"**{alert['name']}**")
            c2.markdown(f"<span style='color:#555;font-size:12px'>{cond_str}</span>", unsafe_allow_html=True)
            with c3:
                if st.button("Remove", key=f"del_alert_{i}"):
                    st.session_state.alerts[i]["active"] = False
                    st.rerun()
            st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Check & send</div>", unsafe_allow_html=True)
        st.caption("Manually trigger a check — background thread also checks every 60 seconds")
        if st.button("Check alerts now", use_container_width=True):
            triggered = 0
            for alert in st.session_state.alerts:
                if not alert["active"]:
                    continue
                try:
                    hist    = yf.Ticker(alert["ticker"]).history(period="1mo")
                    if len(hist) < 2:
                        continue
                    cp      = hist['Close'].iloc[-1]
                    prev    = hist['Close'].iloc[-2]
                    day_chg = ((cp - prev) / prev) * 100
                    avg_vol = hist['Volume'].iloc[:-1].mean()
                    cur_vol = hist['Volume'].iloc[-1]
                    rsi_v   = compute_rsi(hist['Close'])
                    cur_rsi = rsi_v.iloc[-1] if not rsi_v.empty else 50

                    conditions_met = []
                    pc = alert["price_cond"]
                    pv = alert["price_val"]
                    if pc == "Price rises above ₹" and cp > pv:
                        conditions_met.append(f"Price ₹{cp:,.2f} above ₹{pv:,.2f}")
                    elif pc == "Price drops below ₹" and cp < pv:
                        conditions_met.append(f"Price ₹{cp:,.2f} below ₹{pv:,.2f}")
                    elif pc == "Day change rises above %" and day_chg > pv:
                        conditions_met.append(f"Day change {day_chg:+.2f}% > +{pv:.1f}%")
                    elif pc == "Day change drops below %" and day_chg < -pv:
                        conditions_met.append(f"Day change {day_chg:+.2f}% < -{pv:.1f}%")
                    vc = alert["vol_cond"]
                    if vc == "Volume is 2x average" and cur_vol > avg_vol * 2:
                        conditions_met.append(f"Volume 2x average")
                    elif vc == "Volume is 3x average" and cur_vol > avg_vol * 3:
                        conditions_met.append(f"Volume 3x average")
                    rc = alert["rsi_cond"]
                    if rc == "RSI overbought (> 70)" and cur_rsi > 70:
                        conditions_met.append(f"RSI overbought {cur_rsi:.1f}")
                    elif rc == "RSI oversold (< 30)" and cur_rsi < 30:
                        conditions_met.append(f"RSI oversold {cur_rsi:.1f}")

                    total_conditions = sum([1 for x in [alert["price_cond"],
                        alert["vol_cond"], alert["rsi_cond"]] if x != "-- None --"])
                    if len(conditions_met) == total_conditions and total_conditions > 0:
                        sent = send_alert_email(alert["recipient"], alert["name"],
                            " · ".join(conditions_met), cp, day_chg)
                        if sent:
                            triggered += 1
                            st.session_state.alert_log.append({
                                "stock": alert["name"],
                                "trigger": " · ".join(conditions_met),
                                "time": datetime.now().strftime("%d %b %Y · %I:%M %p"),
                                "sent_to": alert["recipient"],
                            })
                except Exception as e:
                    st.error(f"Error checking {alert['name']}: {e}")

            if triggered > 0:
                st.success(f"{triggered} alert(s) triggered — emails sent.")
            else:
                st.info("No alerts triggered right now.")

        if st.session_state.alert_log:
            st.markdown("<div class='nw-section'>Alert history</div>", unsafe_allow_html=True)
            for log in reversed(st.session_state.alert_log[-10:]):
                st.markdown(
                    f"<span style='color:#f0f0f0;font-size:13px'><b>{log['stock']}</b> — {log['trigger']}</span>"
                    f"<br><span style='color:#444;font-size:11px'>{log['time']} · sent to {log['sent_to']}</span>",
                    unsafe_allow_html=True)
                st.markdown("<hr style='margin:8px 0;border:none;border-top:1px solid #1a1a1a'>", unsafe_allow_html=True)
    else:
        st.info("No alerts yet — create your first one above.")

# ════════════════════════════════════════════════════════════
# PAGE: REPORT CARD
# ════════════════════════════════════════════════════════════

elif page == "Report Card":

    st.markdown("## Monthly Report Card")
    st.caption("Your portfolio performance — generated and ready to share")

    if not st.session_state.get("holdings"):
        st.info("Add stocks to your portfolio first, then generate your report card.")
    else:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        import io

        rows           = []
        total_invested = 0
        total_current  = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Ticker"])
            if not cp:
                continue
            hist2    = load_history(h["Ticker"], "2d")
            prev_p   = hist2['Close'].iloc[-2] if len(hist2) >= 2 else cp
            invested = h["Qty"] * h["Buy Price"]
            cur_val  = h["Qty"] * cp
            pnl      = cur_val - invested
            pnl_pct  = (pnl / invested) * 100
            rows.append({
                "stock": h["Stock"], "qty": h["Qty"],
                "buy_price": h["Buy Price"], "cur_price": cp,
                "invested": invested, "cur_val": cur_val,
                "pnl": pnl, "pnl_pct": pnl_pct,
            })
            total_invested += invested
            total_current  += cur_val

        total_pnl     = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
        nifty_return  = get_nifty_return()
        best          = max(rows, key=lambda x: x["pnl_pct"]) if rows else None
        worst         = min(rows, key=lambda x: x["pnl_pct"]) if rows else None

        st.markdown("<div class='nw-section'>Portfolio summary</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Invested</div>
              <div class="nw-metric-value">₹{total_invested:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">₹{total_current:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            dc = "nw-metric-delta-up" if total_pnl >= 0 else "nw-metric-delta-down"
            sg = "+" if total_pnl >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Total P&L</div>
              <div class="nw-metric-value">₹{sg}{total_pnl:,.0f}</div>
              <div class="{dc}">{sg}{total_pnl_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            nc = "nw-metric-delta-up" if total_pnl_pct >= nifty_return else "nw-metric-delta-down"
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">vs Nifty 50</div>
              <div class="nw-metric-value">{'+' if nifty_return>=0 else ''}{nifty_return:.2f}%</div>
              <div class="{nc}">You: {sg}{total_pnl_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)

        if best and worst:
            st.markdown("<div class='nw-section'>Best & worst</div>", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            with b1:
                st.markdown(f"""<div class="nw-metric">
                  <div class="nw-metric-label">Best holding</div>
                  <div class="nw-metric-value" style="color:#4ade80">{best['stock']}</div>
                  <div class="nw-metric-delta-up">+{best['pnl_pct']:.2f}% · +₹{best['pnl']:,.0f}</div>
                </div>""", unsafe_allow_html=True)
            with b2:
                ws = "+" if worst['pnl'] >= 0 else ""
                wc = "nw-metric-delta-up" if worst['pnl'] >= 0 else "nw-metric-delta-down"
                st.markdown(f"""<div class="nw-metric">
                  <div class="nw-metric-label">Worst holding</div>
                  <div class="nw-metric-value" style="color:#f87171">{worst['stock']}</div>
                  <div class="{wc}">{ws}{worst['pnl_pct']:.2f}% · {ws}₹{worst['pnl']:,.0f}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Download</div>", unsafe_allow_html=True)
        if st.button("Generate PDF report card", use_container_width=True):
            buffer = io.BytesIO()
            doc    = SimpleDocTemplate(buffer, pagesize=A4,
                leftMargin=20*mm, rightMargin=20*mm,
                topMargin=20*mm, bottomMargin=20*mm)

            BLACK = colors.HexColor("#0a0a0a")
            GREY  = colors.HexColor("#888888")

            title_style = ParagraphStyle("title", fontSize=28, textColor=BLACK,
                fontName="Helvetica-Bold", spaceAfter=4, leading=32)
            sub_style   = ParagraphStyle("sub", fontSize=11, textColor=GREY,
                fontName="Helvetica", spaceAfter=20)
            sec_style   = ParagraphStyle("sec", fontSize=9, textColor=GREY,
                fontName="Helvetica-Bold", spaceBefore=20, spaceAfter=8, leading=12)
            body_style  = ParagraphStyle("body", fontSize=11, textColor=BLACK,
                fontName="Helvetica", spaceAfter=6, leading=16)

            story = []
            story.append(Paragraph("Voltr", title_style))
            story.append(Paragraph(f"Portfolio Report · {datetime.now().strftime('%B %Y')}", sub_style))
            story.append(HRFlowable(width="100%", thickness=0.5,
                color=colors.HexColor("#e0e0e0"), spaceAfter=16))

            story.append(Paragraph("Portfolio Summary", sec_style))
            pnl_sign = "+" if total_pnl >= 0 else ""
            nif_sign = "+" if nifty_return >= 0 else ""
            beat     = "Outperformed" if total_pnl_pct >= nifty_return else "Underperformed"
            summary_data = [
                ["Metric", "Value"],
                ["Total invested",  f"Rs {total_invested:,.0f}"],
                ["Current value",   f"Rs {total_current:,.0f}"],
                ["Total P&L",       f"{pnl_sign}Rs {total_pnl:,.0f} ({pnl_sign}{total_pnl_pct:.2f}%)"],
                ["Nifty 50 return", f"{nif_sign}{nifty_return:.2f}%"],
                ["vs Benchmark",    f"{beat} by {abs(total_pnl_pct - nifty_return):.2f}%"],
                ["Holdings",        str(len(rows))],
            ]
            t1 = Table(summary_data, colWidths=[80*mm, 90*mm])
            t1.setStyle(TableStyle([
                ("BACKGROUND",  (0,0),(-1,0), colors.HexColor("#f5f5f5")),
                ("TEXTCOLOR",   (0,0),(-1,0), GREY),
                ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0),(-1,0), 8),
                ("FONTNAME",    (0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",    (0,1),(-1,-1), 10),
                ("TEXTCOLOR",   (0,1),(-1,-1), BLACK),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#fafafa")]),
                ("GRID",        (0,0),(-1,-1), 0.25, colors.HexColor("#e0e0e0")),
                ("LEFTPADDING", (0,0),(-1,-1), 10),
                ("RIGHTPADDING",(0,0),(-1,-1), 10),
                ("TOPPADDING",  (0,0),(-1,-1), 8),
                ("BOTTOMPADDING",(0,0),(-1,-1),8),
            ]))
            story.append(t1)

            story.append(Paragraph("Holdings Breakdown", sec_style))
            hold_data = [["Stock","Qty","Buy Price","Current","P&L","P&L %"]]
            for r in sorted(rows, key=lambda x: x["pnl_pct"], reverse=True):
                ps = "+" if r["pnl"] >= 0 else ""
                hold_data.append([r["stock"], str(r["qty"]),
                    f"Rs {r['buy_price']:,.2f}", f"Rs {r['cur_price']:,.2f}",
                    f"{ps}Rs {r['pnl']:,.0f}", f"{ps}{r['pnl_pct']:.2f}%"])
            t2 = Table(hold_data, colWidths=[45*mm,15*mm,30*mm,30*mm,30*mm,20*mm])
            t2.setStyle(TableStyle([
                ("BACKGROUND",  (0,0),(-1,0), colors.HexColor("#f5f5f5")),
                ("TEXTCOLOR",   (0,0),(-1,0), GREY),
                ("FONTNAME",    (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE",    (0,0),(-1,0), 8),
                ("FONTNAME",    (0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",    (0,1),(-1,-1), 9),
                ("TEXTCOLOR",   (0,1),(-1,-1), BLACK),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#fafafa")]),
                ("GRID",        (0,0),(-1,-1), 0.25, colors.HexColor("#e0e0e0")),
                ("LEFTPADDING", (0,0),(-1,-1), 8),
                ("RIGHTPADDING",(0,0),(-1,-1), 8),
                ("TOPPADDING",  (0,0),(-1,-1), 7),
                ("BOTTOMPADDING",(0,0),(-1,-1),7),
            ]))
            story.append(t2)

            if best and worst:
                story.append(Paragraph("Highlights", sec_style))
                bs = "+" if best['pnl'] >= 0 else ""
                ws = "+" if worst['pnl'] >= 0 else ""
                story.append(Paragraph(
                    f"<b>Best:</b> {best['stock']} — {bs}{best['pnl_pct']:.2f}% ({bs}Rs {best['pnl']:,.0f})",
                    body_style))
                story.append(Paragraph(
                    f"<b>Worst:</b> {worst['stock']} — {ws}{worst['pnl_pct']:.2f}% ({ws}Rs {worst['pnl']:,.0f})",
                    body_style))

            story.append(Spacer(1, 20*mm))
            story.append(HRFlowable(width="100%", thickness=0.5,
                color=colors.HexColor("#e0e0e0"), spaceAfter=8))
            story.append(Paragraph(
                f"Generated by Voltr · {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
                ParagraphStyle("footer", fontSize=9, textColor=GREY, fontName="Helvetica")))

            doc.build(story)
            buffer.seek(0)
            st.download_button(label="Download PDF", data=buffer,
                file_name=f"voltr_report_{datetime.now().strftime('%B_%Y').lower()}.pdf",
                mime="application/pdf", use_container_width=True)
            st.success("Report generated. Click Download PDF above.")

# ════════════════════════════════════════════════════════════
# PAGE: MARKET SIGNALS
# ════════════════════════════════════════════════════════════

elif page == "Market Signals":

    st.markdown("## Market Signals")
    st.caption("How Voltr attribution works")
    st.markdown("---")
    st.markdown("""
When a stock in your portfolio moves more than **1%** in a day, Voltr automatically:

1. Fetches the price change for its 3 closest sector peers
2. Calculates the average peer move
3. Determines whether the move is **market-wide** or **company-specific**
4. Surfaces recent news headlines so you know *why*, not just *what*

Add stocks to your portfolio to see live signals on the Portfolio page.
    """)