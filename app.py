import streamlit as st
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
import yfinance as yf
import requests_cache
requests_cache.install_cache("voltr_cache", expire_after=300)
from rapidfuzz import process, fuzz
# ── API keys ──────────────────────────────────────────────
AV_API_KEY   = "0dc8573a97f14da786a314e00c98c112"  # Alpha Vantage
NEWS_API_KEY = "2eef45892af14f5b91ea0338619e3d39"  # NewsAPI

# ── email config ──────────────────────────────────────────
SENDER_EMAIL    = "noreply.voltr@gmail.com"
SENDER_PASSWORD = "rdnsikttgcaeqrje"

# ════════════════════════════════════════════════════════
# DATA LAYER — three specialized sources
# ════════════════════════════════════════════════════════

# ── 1. Indian + US stocks via yfinance ───────────────────
STOCK_UNIVERSE = {
    # Indian stocks
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
    "Tata Motors": "TATAMOTORS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "ONGC": "ONGC.NS",
    "Coal India": "COALINDIA.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Hindalco": "HINDALCO.NS",
    "Bajaj Auto": "BAJAJ-AUTO.NS",
    "Hero MotoCorp": "HEROMOTOCO.NS",
    "Nykaa": "NYKAA.NS",
    "Dmart": "DMART.NS",
    "Vedanta": "VEDL.NS",
    "Paytm": "ONE97.NS",
    # US stocks
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Google": "GOOGL",
    "Amazon": "AMZN",
    "Tesla": "TSLA",
    "Meta": "META",
    "Nvidia": "NVDA",
    "Netflix": "NFLX",
    "Berkshire Hathaway": "BRK-B",
    "JPMorgan Chase": "JPM",
}

# ── 2. Crypto via CoinGecko (no key needed) ───────────────
CRYPTO_UNIVERSE = {
    "Bitcoin": "bitcoin",
    "Ethereum": "ethereum",
    "Solana": "solana",
    "XRP": "ripple",
    "BNB": "binancecoin",
    "Dogecoin": "dogecoin",
    "Cardano": "cardano",
    "Avalanche": "avalanche-2",
    "Polygon": "matic-network",
    "Chainlink": "chainlink",
}

# ── 3. Commodities + Forex via Alpha Vantage ─────────────
COMMODITY_UNIVERSE = {
    "Gold (XAU/USD)":        ("commodity", "XAU"),
    "Silver (XAG/USD)":      ("commodity", "XAG"),
    "Crude Oil WTI":         ("commodity", "WTI"),
    "Natural Gas":           ("commodity", "NGAS"),
    "Copper":                ("commodity", "COPPER"),
    "Wheat":                 ("commodity", "WHEAT"),
}

FOREX_UNIVERSE = {
    "USD/INR":  ("forex", "USD", "INR"),
    "EUR/INR":  ("forex", "EUR", "INR"),
    "GBP/INR":  ("forex", "GBP", "INR"),
    "EUR/USD":  ("forex", "EUR", "USD"),
    "GBP/USD":  ("forex", "GBP", "USD"),
    "JPY/USD":  ("forex", "JPY", "USD"),
}

# combined universe for search
FULL_UNIVERSE = {}
for k in STOCK_UNIVERSE:
    FULL_UNIVERSE[k] = ("stock", k)
for k in CRYPTO_UNIVERSE:
    FULL_UNIVERSE[f"{k} (Crypto)"] = ("crypto", k)
for k in COMMODITY_UNIVERSE:
    FULL_UNIVERSE[k] = ("commodity", k)
for k in FOREX_UNIVERSE:
    FULL_UNIVERSE[k] = ("forex", k)

# ── sector peers (stocks only) ────────────────────────────
SECTOR_PEERS = {
    "RELIANCE.NS":   ["ONGC.NS", "IOC.NS", "BPCL.NS"],
    "TCS.NS":        ["INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "HDFCBANK.NS":   ["ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "INFY.NS":       ["TCS.NS", "WIPRO.NS", "HCLTECH.NS"],
    "ICICIBANK.NS":  ["HDFCBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
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
    "ZOMATO.NS":     ["NYKAA.NS", "DMART.NS", "TATAMOTORS.NS"],
    "TATAMOTORS.NS": ["MARUTI.NS", "LT.NS", "BAJFINANCE.NS"],
    "TATASTEEL.NS":  ["JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS"],
    "AAPL":          ["MSFT", "GOOGL", "META"],
    "MSFT":          ["AAPL", "GOOGL", "AMZN"],
    "TSLA":          ["AAPL", "AMZN", "NVDA"],
}

# ════════════════════════════════════════════════════════
# FETCH FUNCTIONS
# ════════════════════════════════════════════════════════

def get_asset_type(name):
    clean = name.replace(" (Crypto)", "")
    if name in STOCK_UNIVERSE:
        return "stock"
    if clean in CRYPTO_UNIVERSE or name in CRYPTO_UNIVERSE:
        return "crypto"
    if name in COMMODITY_UNIVERSE:
        return "commodity"
    if name in FOREX_UNIVERSE:
        return "forex"
    return "stock"

@st.cache_data(ttl=300)
def load_history(asset_name, period="3mo"):
    atype = get_asset_type(asset_name)

    if atype == "stock":
        ticker = STOCK_UNIVERSE.get(asset_name, asset_name)
        try:
            data = yf.Ticker(ticker).history(period=period)
            if not data.empty:
                return data, "₹" if ".NS" in ticker else "$"
        except:
            pass
        return pd.DataFrame(), "₹"

    elif atype == "crypto":
        clean   = asset_name.replace(" (Crypto)", "")
        coin_id = CRYPTO_UNIVERSE.get(clean, clean.lower())
        days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        days = days_map.get(period, 90)
        try:
            url  = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            resp = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=10)
            data = resp.json()
            prices = data.get("prices", [])
            if prices:
                df = pd.DataFrame(prices, columns=["timestamp", "Close"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
                df["Open"]  = df["Close"].shift(1).fillna(df["Close"])
                df["High"]  = df["Close"] * 1.005
                df["Low"]   = df["Close"] * 0.995
                df["Volume"] = 0
                return df, "$"
        except:
            pass
        return pd.DataFrame(), "$"

    elif atype == "commodity":
        _, symbol = COMMODITY_UNIVERSE[asset_name]
        try:
            url  = "https://www.alphavantage.co/query"
            resp = requests.get(url, params={
                "function": "COMMODITY_EXCHANGE_RATE" if symbol in ["XAU","XAG"] else "REAL_GDP",
                "from_symbol": symbol,
                "to_symbol": "USD",
                "apikey": AV_API_KEY
            }, timeout=10)
            # fallback to yfinance commodity ETFs
            etf_map = {
                "XAU": "GLD", "XAG": "SLV",
                "WTI": "USO", "NGAS": "UNG",
                "COPPER": "CPER", "WHEAT": "WEAT"
            }
            etf = etf_map.get(symbol, "GLD")
            data = yf.Ticker(etf).history(period=period)
            if not data.empty:
                return data, "$"
        except:
            pass
        return pd.DataFrame(), "$"

    elif atype == "forex":
        _, from_c, to_c = FOREX_UNIVERSE[asset_name]
        try:
            url  = "https://www.alphavantage.co/query"
            resp = requests.get(url, params={
                "function": "FX_DAILY",
                "from_symbol": from_c,
                "to_symbol": to_c,
                "outputsize": "compact",
                "apikey": AV_API_KEY
            }, timeout=10)
            data = resp.json()
            ts   = data.get("Time Series FX (Daily)", {})
            if ts:
                rows = []
                for date, vals in sorted(ts.items()):
                    rows.append({
                        "timestamp": pd.to_datetime(date),
                        "Open":  float(vals["1. open"]),
                        "High":  float(vals["2. high"]),
                        "Low":   float(vals["3. low"]),
                        "Close": float(vals["4. close"]),
                        "Volume": 0,
                    })
                df = pd.DataFrame(rows).set_index("timestamp")
                return df, to_c
        except:
            pass
        return pd.DataFrame(), ""

    return pd.DataFrame(), ""

@st.cache_data(ttl=300)
def get_current_price(asset_name):
    atype = get_asset_type(asset_name)

    if atype == "stock":
        ticker = STOCK_UNIVERSE.get(asset_name, asset_name)
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if not hist.empty:
                return hist['Close'].iloc[-1]
        except:
            pass
        return None

    elif atype == "crypto":
        clean   = asset_name.replace(" (Crypto)", "")
        coin_id = CRYPTO_UNIVERSE.get(clean, clean.lower())
        try:
            url  = f"https://api.coingecko.com/api/v3/simple/price"
            resp = requests.get(url, params={
                "ids": coin_id, "vs_currencies": "usd"
            }, timeout=10)
            data = resp.json()
            return data.get(coin_id, {}).get("usd")
        except:
            return None

    elif atype in ("commodity", "forex"):
        hist, _ = load_history(asset_name, "1mo")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return None

    return None

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

@st.cache_data(ttl=600)
def get_news(company_name):
    try:
        url  = (
            f"https://newsapi.org/v2/everything?"
            f"q={company_name}+stock+India&"
            f"language=en&sortBy=publishedAt&pageSize=5&"
            f"apiKey={NEWS_API_KEY}"
        )
        r    = requests.get(url, timeout=5)
        data = r.json()
        if data.get("status") == "ok":
            return data.get("articles", [])
    except:
        pass
    return []

def search_assets(query):
    if not query or len(query) < 2:
        return {k: k for k in list(FULL_UNIVERSE.keys())[:30]}

    all_names = list(FULL_UNIVERSE.keys())

    # exact substring matches first
    exact = [k for k in all_names if query.lower() in k.lower()]

    # fuzzy matches for typos
    fuzzy_results = process.extract(
        query, all_names,
        scorer=fuzz.WRatio,
        limit=10,
        score_cutoff=50
    )
    fuzzy_names = [r[0] for r in fuzzy_results]

    # combine — exact first, then fuzzy, deduplicated
    combined = list(dict.fromkeys(exact + fuzzy_names))

    return {k: k for k in combined} if combined else \
           {k: k for k in list(FULL_UNIVERSE.keys())[:30]}

def analyze_move(asset_name, day_change_pct):
    ticker     = STOCK_UNIVERSE.get(asset_name)
    peers      = SECTOR_PEERS.get(ticker, []) if ticker else []
    peer_moves = get_peer_moves(tuple(peers)) if peers else {}
    valid      = [v for v in peer_moves.values() if v is not None]
    avg_peer   = round(sum(valid) / len(valid), 2) if valid else 0
    same_dir   = (day_change_pct > 0 and avg_peer > 0) or \
                 (day_change_pct < 0 and avg_peer < 0)
    if same_dir and abs(avg_peer) > 0.5:
        verdict     = "market-wide"
        explanation = (
            f"Sector peers also averaged {avg_peer:+.2f}% today. "
            f"Broad sector or market move — not specific to this stock."
        )
    else:
        verdict     = "company-specific"
        explanation = (
            f"Peers moved only {avg_peer:+.2f}% while this moved "
            f"{day_change_pct:+.2f}%. Appears company-specific."
        ) if peers else f"This asset moved {day_change_pct:+.2f}% today."
    return verdict, explanation, peer_moves

@st.cache_data(ttl=3600)
def get_beta(asset_name):
    ticker = STOCK_UNIVERSE.get(asset_name)
    if not ticker:
        return 1.0
    try:
        sh = yf.Ticker(ticker).history(period="1y")
        nh = yf.Ticker("^NSEI").history(period="1y")
        if sh.empty or nh.empty:
            return 1.0
        sr  = sh['Close'].pct_change().dropna()
        nr  = nh['Close'].pct_change().dropna()
        com = pd.DataFrame({"s": sr, "n": nr}).dropna()
        if len(com) < 30:
            return 1.0
        cov = com['s'].cov(com['n'])
        var = com['n'].var()
        return round(cov / var, 2) if var != 0 else 1.0
    except:
        return 1.0

@st.cache_data(ttl=3600)
def get_nifty_return():
    try:
        hist = yf.Ticker("^NSEI").history(period="1mo")
        if len(hist) >= 2:
            return ((hist['Close'].iloc[-1] - hist['Close'].iloc[0])
                    / hist['Close'].iloc[0]) * 100
    except:
        pass
    return 0.0
@st.cache_data(ttl=3600)
def get_stock_financials(asset_name):
    ticker = STOCK_UNIVERSE.get(asset_name)
    if not ticker:
        return None
    try:
        info = yf.Ticker(ticker).info
        return {
            "market_cap":    info.get("marketCap"),
            "pe_ratio":      info.get("trailingPE"),
            "pb_ratio":      info.get("priceToBook"),
            "revenue":       info.get("totalRevenue"),
            "profit_margin": info.get("profitMargins"),
            "dividend":      info.get("dividendYield"),
            "52w_high":      info.get("fiftyTwoWeekHigh"),
            "52w_low":       info.get("fiftyTwoWeekLow"),
            "sector":        info.get("sector", ""),
            "industry":      info.get("industry", ""),
        }
    except:
        return None
# ════════════════════════════════════════════════════════
# EMAIL + ALERTS
# ════════════════════════════════════════════════════════

def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

def send_alert_email(recipient, stock_name, trigger_desc, current_price, day_chg):
    try:
        msg            = MIMEMultipart("alternative")
        chg_color      = "#4ade80" if day_chg >= 0 else "#f87171"
        chg_sign       = "+" if day_chg >= 0 else ""
        msg["Subject"] = f"Voltr Alert — {stock_name} triggered"
        msg["From"]    = SENDER_EMAIL
        msg["To"]      = recipient
        html = f"""
        <html><body style="font-family:-apple-system,sans-serif;background:#0a0a0a;
                           color:#f0f0f0;padding:40px 20px">
          <div style="max-width:480px;margin:0 auto">
            <p style="font-size:13px;font-weight:600;color:#555;letter-spacing:2px">VOLTR</p>
            <h1 style="font-size:24px;font-weight:600;color:#f0f0f0;letter-spacing:-0.5px">
              Alert triggered</h1>
            <p style="font-size:13px;color:#555">{datetime.now().strftime("%d %b %Y · %I:%M %p")}</p>
            <div style="background:#141414;border:1px solid #1e1e1e;border-radius:16px;padding:28px;margin:20px 0">
              <p style="font-size:13px;color:#555;text-transform:uppercase">Stock</p>
              <p style="font-size:22px;font-weight:600;color:#f0f0f0">{stock_name}</p>
              <p style="font-size:13px;color:#555;text-transform:uppercase">Trigger</p>
              <p style="font-size:15px;color:#f0f0f0">{trigger_desc}</p>
              <p style="font-size:20px;font-weight:600;color:#f0f0f0">
                {current_price:,.2f}
                <span style="color:{chg_color};margin-left:12px">{chg_sign}{day_chg:.2f}%</span>
              </p>
            </div>
            <p style="font-size:12px;color:#333">Sent by Voltr</p>
          </div>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
        return True
    except:
        return False

def check_and_fire_alerts(alerts, alert_log):
    while True:
        for alert in alerts:
            if not alert.get("active"):
                continue
            try:
                cp = get_current_price(alert["name"])
                if not cp:
                    continue
                hist, _ = load_history(alert["name"], "1mo")
                if hist.empty or len(hist) < 2:
                    continue
                prev    = hist['Close'].iloc[-2]
                day_chg = ((cp - prev) / prev) * 100
                avg_vol = hist['Volume'].iloc[:-1].mean() if 'Volume' in hist else 0
                cur_vol = hist['Volume'].iloc[-1] if 'Volume' in hist else 0
                rsi_v   = compute_rsi(hist['Close'])
                cur_rsi = rsi_v.iloc[-1] if not rsi_v.empty else 50

                conditions_met = []
                pc = alert["price_cond"]
                pv = alert["price_val"]
                if pc == "Price rises above" and cp > pv:
                    conditions_met.append(f"Price {cp:,.2f} above {pv:,.2f}")
                elif pc == "Price drops below" and cp < pv:
                    conditions_met.append(f"Price {cp:,.2f} below {pv:,.2f}")
                elif pc == "Day change rises above %" and day_chg > pv:
                    conditions_met.append(f"Day change {day_chg:+.2f}% > +{pv:.1f}%")
                elif pc == "Day change drops below %" and day_chg < -pv:
                    conditions_met.append(f"Day change {day_chg:+.2f}% < -{pv:.1f}%")

                vc = alert["vol_cond"]
                if vc == "Volume is 2x average" and avg_vol > 0 and cur_vol > avg_vol * 2:
                    conditions_met.append("Volume 2x average")
                elif vc == "Volume is 3x average" and avg_vol > 0 and cur_vol > avg_vol * 3:
                    conditions_met.append("Volume 3x average")

                rc = alert["rsi_cond"]
                if rc == "RSI overbought (> 70)" and cur_rsi > 70:
                    conditions_met.append(f"RSI overbought {cur_rsi:.1f}")
                elif rc == "RSI oversold (< 30)" and cur_rsi < 30:
                    conditions_met.append(f"RSI oversold {cur_rsi:.1f}")

                total = sum([1 for x in [alert["price_cond"], alert["vol_cond"],
                             alert["rsi_cond"]] if x != "-- None --"])
                if len(conditions_met) == total and total > 0:
                    sent = send_alert_email(alert["recipient"], alert["name"],
                        " · ".join(conditions_met), cp, day_chg)
                    if sent:
                        alert_log.append({
                            "stock": alert["name"],
                            "trigger": " · ".join(conditions_met),
                            "time": datetime.now().strftime("%d %b %Y · %I:%M %p"),
                            "sent_to": alert["recipient"],
                        })
            except:
                continue
        time.sleep(60)

if "bg_thread_started" not in st.session_state:
    st.session_state.bg_thread_started = True
    st.session_state.alerts            = []
    st.session_state.alert_log         = []
    threading.Thread(
        target=check_and_fire_alerts,
        args=(st.session_state.alerts, st.session_state.alert_log),
        daemon=True
    ).start()

# ════════════════════════════════════════════════════════
# PAGE CONFIG + CSS
# ════════════════════════════════════════════════════════

st.set_page_config(page_title="Voltr", page_icon="V",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
#MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
[data-testid="stSidebar"] {background:#0f0f0f;border-right:1px solid #1e1e1e;}
[data-testid="stSidebar"] * {color:#a0a0a0 !important;}
.stApp {background:#0a0a0a;}
.nw-metric {background:#141414;border:1px solid #1e1e1e;border-radius:12px;padding:18px 20px;}
.nw-metric-label {font-size:11px;color:#555;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:8px;}
.nw-metric-value {font-size:22px;font-weight:600;color:#f0f0f0;letter-spacing:-0.5px;}
.nw-metric-delta-up {font-size:12px;color:#4ade80;margin-top:4px;}
.nw-metric-delta-down {font-size:12px;color:#f87171;margin-top:4px;}
.nw-signal {background:#141414;border:1px solid #1e1e1e;border-radius:12px;padding:16px 20px;margin-bottom:10px;}
.nw-signal-header {display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
.nw-signal-name {font-size:14px;font-weight:600;color:#f0f0f0;}
.nw-badge-warn {background:#2a1f00;color:#f59e0b;font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500;}
.nw-badge-ok {background:#0f1f0f;color:#4ade80;font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500;}
.nw-verdict {font-size:13px;color:#888;line-height:1.6;margin-bottom:10px;}
.nw-peer-row {display:flex;gap:8px;flex-wrap:wrap;}
.nw-peer-chip {background:#1a1a1a;border:1px solid #2a2a2a;border-radius:6px;padding:4px 10px;font-size:11px;color:#888;}
.nw-peer-chip b {color:#f0f0f0;}
.nw-news-item {padding:10px 0;border-bottom:1px solid #1e1e1e;font-size:13px;}
.nw-news-item a {color:#a0a0a0;text-decoration:none;}
.nw-news-item a:hover {color:#f0f0f0;}
.nw-news-source {font-size:11px;color:#444;margin-top:3px;}
.nw-section {font-size:11px;font-weight:600;color:#555;text-transform:uppercase;letter-spacing:0.8px;margin:28px 0 14px;}
.asset-tag {display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;margin-left:6px;}
.tag-stock {background:#1a2a1a;color:#4ade80;}
.tag-crypto {background:#2a1a2a;color:#a78bfa;}
.tag-commodity {background:#2a2a1a;color:#fbbf24;}
.tag-forex {background:#1a2a2a;color:#60a5fa;}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Voltr")
    st.markdown("---")
    page = st.radio("Navigation",
        ["My Portfolio", "Stock Explorer", "Stress Tester",
         "Behavior Detector", "Sector Heatmap", "Alerts",
         "Report Card", "Market Signals"],
        label_visibility="collapsed")
    st.markdown("---")
    st.caption("Stocks · Crypto · Forex · Commodities")
    st.caption("Signal over noise")

# ════════════════════════════════════════════════════════
# PAGE: MY PORTFOLIO
# ════════════════════════════════════════════════════════

if page == "My Portfolio":
    st.markdown("## My Portfolio")
    st.caption("Stocks, crypto, forex and commodities — all in one place")

    if "holdings" not in st.session_state:
        st.session_state.holdings = []

    with st.expander("+ Add a holding",
                     expanded=len(st.session_state.holdings) == 0):
        st.caption("Search any stock, crypto, commodity or forex pair")
        search_query = st.text_input("Search asset",
            placeholder="e.g. Zomato, Bitcoin, Gold, USD/INR...",
            key="stock_search")
        results = search_assets(search_query)

        if results:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                asset_display = st.selectbox("Select asset",
                    list(results.keys()), key="stock_select")
                atype = get_asset_type(asset_display)
                tag_map = {"stock":"tag-stock","crypto":"tag-crypto",
                           "commodity":"tag-commodity","forex":"tag-forex"}
                st.markdown(
                    f'<span class="asset-tag {tag_map.get(atype,"")}">'+
                    f'{atype.upper()}</span>', unsafe_allow_html=True)
            with c2:
                quantity  = st.number_input("Quantity", min_value=0.0001,
                    value=1.0, step=0.01, format="%.4f")
            with c3:
                buy_price = st.number_input("Avg buy price",
                    min_value=0.0001, value=100.0, step=0.01, format="%.2f")
            with c4:
                st.write("")
                st.write("")
                if st.button("Add", use_container_width=True):
                    _, cur = load_history(asset_display, "1mo")
                    st.session_state.holdings.append({
                        "Name":      asset_display,
                        "Type":      atype,
                        "Qty":       quantity,
                        "Buy Price": buy_price,
                        "Currency":  cur if cur else "$",
                    })
                    st.rerun()
        else:
            st.warning("No results found.")

    if st.session_state.holdings:
        rows           = []
        total_invested = 0
        total_current  = 0
        today_pnl      = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Name"])
            if cp:
                hist, currency = load_history(h["Name"], "2d")
                prev_p   = hist['Close'].iloc[-2] if len(hist) >= 2 else cp
                day_chg  = ((cp - prev_p) / prev_p) * 100
                invested = h["Qty"] * h["Buy Price"]
                cur_val  = h["Qty"] * cp
                pnl      = cur_val - invested
                pnl_pct  = (pnl / invested) * 100
                today_mv = h["Qty"] * (cp - prev_p)
                rows.append({
                    "name": h["Name"], "type": h["Type"],
                    "qty": h["Qty"], "buy_price": h["Buy Price"],
                    "cur_price": cp, "currency": currency,
                    "invested": invested, "cur_val": cur_val,
                    "pnl": pnl, "pnl_pct": pnl_pct,
                    "day_chg": day_chg, "today_mv": today_mv,
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
              <div class="nw-metric-value">{total_invested:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">{total_current:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            dc = "nw-metric-delta-up" if total_pnl >= 0 else "nw-metric-delta-down"
            sg = "+" if total_pnl >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Total P&L</div>
              <div class="nw-metric-value">{sg}{total_pnl:,.2f}</div>
              <div class="{dc}">{sg}{total_pnl_pct:.2f}% all time</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            tc = "nw-metric-delta-up" if today_pnl >= 0 else "nw-metric-delta-down"
            ts = "+" if today_pnl >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Today</div>
              <div class="nw-metric-value">{ts}{today_pnl:,.2f}</div>
              <div class="{tc}">{ts}{today_pct:.2f}% today</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Holdings</div>",
                    unsafe_allow_html=True)

        tag_map = {"stock":"tag-stock","crypto":"tag-crypto",
                   "commodity":"tag-commodity","forex":"tag-forex"}
        for r in rows:
            pc = "#4ade80" if r["pnl"] >= 0 else "#f87171"
            dc = "#4ade80" if r["day_chg"] >= 0 else "#f87171"
            ps = "+" if r["pnl"] >= 0 else ""
            ds = "+" if r["day_chg"] >= 0 else ""
            c1,c2,c3,c4,c5,c6 = st.columns([3,1,2,2,2,2])
            c1.markdown(
                f"**{r['name']}** "
                f'<span class="asset-tag {tag_map.get(r["type"],"")}">'+
                f'{r["type"].upper()}</span>',
                unsafe_allow_html=True)
            c2.markdown(f"<span style='color:#555'>{r['qty']}</span>",
                        unsafe_allow_html=True)
            c3.markdown(f"<span style='color:#888'>{r['buy_price']:,.2f}</span>",
                        unsafe_allow_html=True)
            currency_label = "₹" if r.get("type") == "stock" and \
                             STOCK_UNIVERSE.get(r["name",""])  and \
                             ".NS" in STOCK_UNIVERSE.get(r["name"], "") \
                             else "$" if r.get("type") in ("stock","crypto","commodity") \
                             else ""
            cur_sym = r.get("currency", "")
            c4.markdown(f"{cur_sym}{r['cur_price']:,.2f}")
            c5.markdown(
                f"<span style='color:{pc}'>{ps}{r['pnl']:,.2f} "
                f"({ps}{r['pnl_pct']:.1f}%)</span>",
                unsafe_allow_html=True)
            c6.markdown(
                f"<span style='color:{dc}'>{ds}{r['day_chg']:.2f}% today</span>",
                unsafe_allow_html=True)
            st.markdown(
                "<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>",
                unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Allocation</div>",
                    unsafe_allow_html=True)
        alloc_df = pd.DataFrame([{"Asset": r["name"], "Value": r["cur_val"]}
                                  for r in rows])
        fig_pie = px.pie(alloc_df, values="Value", names="Asset", hole=0.5,
            color_discrete_sequence=["#a78bfa","#34d399","#60a5fa","#f472b6",
                                      "#fbbf24","#f87171","#38bdf8","#fb923c"])
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0,r=0,t=10,b=0),
            legend=dict(font=dict(color="#888",size=12)), height=300)
        fig_pie.update_traces(textfont_color="#f0f0f0")
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("<div class='nw-section'>Market signals today</div>",
                    unsafe_allow_html=True)
        for r in rows:
            verdict, explanation, peer_moves = analyze_move(r["name"], r["day_chg"])
            badge = ("nw-badge-warn","Company-specific") \
                    if verdict == "company-specific" \
                    else ("nw-badge-ok","Market-wide")
            dc = "#4ade80" if r["day_chg"] >= 0 else "#f87171"
            ds = "+" if r["day_chg"] >= 0 else ""
            peers_html = ""
            for pticker, pmove in peer_moves.items():
                label = pticker.replace(".NS","")
                val   = f"{pmove:+.2f}%" if pmove is not None else "N/A"
                pc    = "#4ade80" if (pmove or 0) >= 0 else "#f87171"
                peers_html += (f'<div class="nw-peer-chip">{label} '
                               f'<b style="color:{pc}">{val}</b></div>')
            articles  = get_news(r["name"])
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
                <span class="nw-signal-name">{r['name']}
                  <span style="color:{dc};font-weight:400;margin-left:6px">
                    {ds}{r['day_chg']:.2f}%</span>
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
        st.info("No holdings yet — add your first asset above.")

# ════════════════════════════════════════════════════════
# PAGE: STOCK EXPLORER
# ════════════════════════════════════════════════════════

elif page == "Stock Explorer":
    st.markdown("## Asset Explorer")
    st.caption("Stocks · Crypto · Commodities · Forex — charts and live stats")

    search_ex = st.sidebar.text_input("Search asset",
        placeholder="e.g. Apple, Bitcoin, Gold...", key="explorer_search")
    ex_results = search_assets(search_ex)
    sel_display = st.sidebar.selectbox("Select", list(ex_results.keys()))
    period      = st.sidebar.selectbox("Period", ["1mo","3mo","6mo","1y"], index=1)
    atype       = get_asset_type(sel_display)

    hist, currency = load_history(sel_display, period)

    if not hist.empty:
        latest = hist['Close'].iloc[-1]
        prev   = hist['Close'].iloc[-2] if len(hist) >= 2 else latest
        chg    = ((latest - prev) / prev) * 100
        sign   = "+" if chg >= 0 else ""
        cc     = "nw-metric-delta-up" if chg >= 0 else "nw-metric-delta-down"

        tag_map = {"stock":"tag-stock","crypto":"tag-crypto",
                   "commodity":"tag-commodity","forex":"tag-forex"}
        st.markdown(
            f"### {sel_display} "
            f'<span class="asset-tag {tag_map.get(atype,"")}">'+
            f'{atype.upper()}</span>',
            unsafe_allow_html=True)

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Price</div>
              <div class="nw-metric-value">{latest:,.2f}</div>
              <div class="{cc}">{sign}{chg:.2f}% today</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Period High</div>
              <div class="nw-metric-value">{hist['High'].max():,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Period Low</div>
              <div class="nw-metric-value">{hist['Low'].min():,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            vol = hist['Volume'].mean() if 'Volume' in hist else 0
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Avg Volume</div>
              <div class="nw-metric-value">{vol:,.0f}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Price chart</div>",
                    unsafe_allow_html=True)
        fig = go.Figure(data=[go.Candlestick(
            x=hist.index,
            open=hist['Open'], high=hist['High'],
            low=hist['Low'],   close=hist['Close'],
            increasing_line_color='#4ade80',
            decreasing_line_color='#f87171',
            name=sel_display
        )])
        fig.update_layout(xaxis_rangeslider_visible=False,
            plot_bgcolor='#0a0a0a', paper_bgcolor='rgba(0,0,0,0)',
            height=460, margin=dict(l=0,r=0,t=10,b=0),
            xaxis=dict(showgrid=False,color="#444"),
            yaxis=dict(showgrid=True,gridcolor='#1a1a1a',color="#444"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown("""
        <div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;
                    padding:24px;text-align:center;margin-top:20px">
          <div style="font-size:16px;color:#555;margin-bottom:8px">Data unavailable</div>
          <div style="font-size:13px;color:#444">
            This asset may be delisted, outside our coverage, or temporarily unavailable.
            Try searching for a different asset.
          </div>
        </div>
        """, unsafe_allow_html=True)
# ── company financials ────────────────────────────
        if atype == "stock":
            fins = get_stock_financials(sel_display)
            if fins:
                st.markdown("<div class='nw-section'>Company financials</div>",
                            unsafe_allow_html=True)
                f1,f2,f3,f4 = st.columns(4)
                with f1:
                    mc = fins["market_cap"]
                    mc_str = f"${mc/1e9:.1f}B" if mc and mc>1e9 else \
                             f"${mc/1e6:.1f}M" if mc else "N/A"
                    st.markdown(f"""<div class="nw-metric">
                      <div class="nw-metric-label">Market Cap</div>
                      <div class="nw-metric-value" style="font-size:18px">{mc_str}</div>
                    </div>""", unsafe_allow_html=True)
                with f2:
                    pe = fins["pe_ratio"]
                    st.markdown(f"""<div class="nw-metric">
                      <div class="nw-metric-label">P/E Ratio</div>
                      <div class="nw-metric-value" style="font-size:18px">
                        {f"{pe:.1f}x" if pe else "N/A"}</div>
                    </div>""", unsafe_allow_html=True)
                with f3:
                    pm = fins["profit_margin"]
                    st.markdown(f"""<div class="nw-metric">
                      <div class="nw-metric-label">Profit Margin</div>
                      <div class="nw-metric-value" style="font-size:18px">
                        {f"{pm*100:.1f}%" if pm else "N/A"}</div>
                    </div>""", unsafe_allow_html=True)
                with f4:
                    div = fins["dividend"]
                    st.markdown(f"""<div class="nw-metric">
                      <div class="nw-metric-label">Dividend Yield</div>
                      <div class="nw-metric-value" style="font-size:18px">
                        {f"{div*100:.2f}%" if div else "N/A"}</div>
                    </div>""", unsafe_allow_html=True)
                if fins.get("sector"):
                    st.markdown(
                        f"<span style='color:#555;font-size:12px'>"
                        f"{fins['sector']} · {fins['industry']}</span>",
                        unsafe_allow_html=True)
# ════════════════════════════════════════════════════════
# PAGE: STRESS TESTER
# ════════════════════════════════════════════════════════

elif page == "Stress Tester":
    st.markdown("## Stress Tester")
    st.caption("See how your portfolio holds up under market shocks")

    if not st.session_state.get("holdings"):
        st.info("Add assets to your portfolio first.")
    else:
        SCENARIOS = {
            "Nifty crashes 10%":             -10.0,
            "Nifty crashes 15%":             -15.0,
            "Nifty crashes 20% (2008-like)": -20.0,
            "Nifty rallies 10%":             +10.0,
            "Global selloff -12%":           -12.0,
            "Crypto crash -40%":             -40.0,
            "Crypto rally +50%":             +50.0,
            "Custom scenario":               None,
        }

        st.markdown("<div class='nw-section'>Choose a scenario</div>",
                    unsafe_allow_html=True)
        col1, col2 = st.columns([2,1])
        with col1:
            sel_scenario = st.selectbox("Scenario", list(SCENARIOS.keys()),
                label_visibility="collapsed")
        with col2:
            if SCENARIOS[sel_scenario] is None:
                market_move = st.number_input("Market move (%)",
                    value=-10.0, min_value=-90.0, max_value=200.0, step=0.5)
            else:
                market_move = SCENARIOS[sel_scenario]
                col = '#f87171' if market_move < 0 else '#4ade80'
                st.markdown(f"""<div class="nw-metric" style="padding:12px 16px">
                  <div class="nw-metric-label">Market move</div>
                  <div class="nw-metric-value" style="font-size:18px;color:{col}">
                    {market_move:+.1f}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Portfolio impact</div>",
                    unsafe_allow_html=True)

        stress_rows    = []
        total_current  = 0
        total_stressed = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Name"])
            if not cp:
                continue
            beta           = get_beta(h["Name"])
            stock_move     = market_move * beta
            stressed_price = cp * (1 + stock_move / 100)
            cur_val        = h["Qty"] * cp
            stressed_val   = h["Qty"] * stressed_price
            impact         = stressed_val - cur_val
            impact_pct     = (impact / cur_val) * 100
            stress_rows.append({
                "name": h["Name"], "type": h["Type"],
                "beta": beta, "cur_price": cp,
                "stressed_price": stressed_price,
                "cur_val": cur_val, "stressed_val": stressed_val,
                "impact": impact, "impact_pct": impact_pct,
            })
            total_current  += cur_val
            total_stressed += stressed_val

        total_impact     = total_stressed - total_current
        total_impact_pct = (total_impact / total_current * 100) if total_current else 0

        m1,m2,m3 = st.columns(3)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">{total_current:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Stressed value</div>
              <div class="nw-metric-value">{total_stressed:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            ic  = "nw-metric-delta-up" if total_impact >= 0 else "nw-metric-delta-down"
            is_ = "+" if total_impact >= 0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Estimated impact</div>
              <div class="nw-metric-value">{is_}{total_impact:,.2f}</div>
              <div class="{ic}">{is_}{total_impact_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        stress_rows.sort(key=lambda x: x["impact"])
        tag_map = {"stock":"tag-stock","crypto":"tag-crypto",
                   "commodity":"tag-commodity","forex":"tag-forex"}
        for r in stress_rows:
            ic  = "#4ade80" if r["impact"] >= 0 else "#f87171"
            is_ = "+" if r["impact"] >= 0 else ""
            bc  = "#4ade80" if r["beta"] < 1 else \
                  "#f59e0b" if r["beta"] < 1.5 else "#f87171"
            bl  = "Low" if r["beta"] < 1 else \
                  "Medium" if r["beta"] < 1.5 else "High"
            c1,c2,c3,c4,c5 = st.columns([3,1,2,2,2])
            c1.markdown(
                f"**{r['name']}** "
                f'<span class="asset-tag {tag_map.get(r["type"],"")}">'+
                f'{r["type"].upper()}</span>',
                unsafe_allow_html=True)
            c2.markdown(
                f"<span style='color:{bc};font-size:12px'>"
                f"β {r['beta']}<br>{bl}</span>",
                unsafe_allow_html=True)
            c3.markdown(
                f"<span style='color:#888'>{r['cur_price']:,.2f}</span>",
                unsafe_allow_html=True)
            c4.markdown(
                f"<span style='color:{ic}'>{r['stressed_price']:,.2f}</span>",
                unsafe_allow_html=True)
            c5.markdown(
                f"<span style='color:{ic}'>{is_}{r['impact']:,.2f} "
                f"({is_}{r['impact_pct']:.1f}%)</span>",
                unsafe_allow_html=True)
            st.markdown(
                "<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>",
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# PAGE: BEHAVIOR DETECTOR
# ════════════════════════════════════════════════════════

elif page == "Behavior Detector":
    st.markdown("## Behavior Detector")
    st.caption("Log your trades and discover what your patterns reveal about you")

    if "trade_log" not in st.session_state:
        st.session_state.trade_log = []

    with st.expander("+ Log a trade",
                     expanded=len(st.session_state.trade_log) == 0):
        tl1,tl2,tl3,tl4,tl5 = st.columns([3,1,2,2,1])
        with tl1:
            t_search  = st.text_input("Search asset",
                placeholder="e.g. Infosys, Bitcoin...", key="trade_search")
            t_results = search_assets(t_search)
            t_display = st.selectbox("Asset", list(t_results.keys()),
                key="trade_stock")
        with tl2:
            t_action = st.selectbox("Action", ["Buy","Sell"], key="trade_action")
        with tl3:
            t_price = st.number_input("Price", min_value=0.0001,
                value=100.0, step=0.01, key="trade_price")
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
                    "stock":    t_display,
                    "action":   t_action,
                    "price":    t_price,
                    "date":     str(t_date),
                    "nifty_3d": round(nifty_3d, 2),
                })
                st.success(f"Logged {t_action} — {t_display} at {t_price:.2f}")
                st.rerun()

    if st.session_state.trade_log:
        st.markdown("<div class='nw-section'>Trade history</div>",
                    unsafe_allow_html=True)
        for t in st.session_state.trade_log:
            ac = "#4ade80" if t["action"] == "Buy" else "#f87171"
            c1,c2,c3,c4 = st.columns([3,1,2,2])
            c1.markdown(f"**{t['stock']}**")
            c2.markdown(f"<span style='color:{ac}'>{t['action']}</span>",
                        unsafe_allow_html=True)
            c3.markdown(f"{t['price']:,.2f}")
            c4.markdown(f"<span style='color:#555'>{t['date']}</span>",
                        unsafe_allow_html=True)
            st.markdown(
                "<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>",
                unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Behavioral analysis</div>",
                    unsafe_allow_html=True)
        tdf  = pd.DataFrame(st.session_state.trade_log)
        buys = tdf[tdf["action"] == "Buy"]

        if len(buys) >= 2:
            fp  = len(buys[buys["nifty_3d"] > 2.0]) / len(buys) * 100
            fc  = "#f87171" if fp > 50 else "#f59e0b" if fp > 25 else "#4ade80"
            fv  = ("Strong FOMO — most buys follow market rallies.") if fp > 50 else \
                  ("Mild FOMO tendency.") if fp > 25 else \
                  ("No significant FOMO pattern.")
            st.markdown(f"""<div class="nw-signal">
              <div class="nw-signal-header">
                <span class="nw-signal-name">FOMO detector</span>
                <span style="color:{fc};font-size:13px;font-weight:600">
                  {fp:.0f}% of buys after rallies</span>
              </div>
              <div class="nw-verdict">{fv}</div>
            </div>""", unsafe_allow_html=True)

        if len(tdf) >= 3:
            tdf["date_parsed"] = pd.to_datetime(tdf["date"])
            dr = (tdf["date_parsed"].max() - tdf["date_parsed"].min()).days
            if dr > 0:
                tpm = len(tdf) / (dr / 30)
                oc  = "#f87171" if tpm > 10 else "#f59e0b" if tpm > 5 else "#4ade80"
                ov  = (f"High frequency — {tpm:.1f} trades/month.") if tpm > 10 else \
                      (f"Moderate — {tpm:.1f} trades/month.") if tpm > 5 else \
                      (f"Patient style — {tpm:.1f} trades/month.")
                st.markdown(f"""<div class="nw-signal">
                  <div class="nw-signal-header">
                    <span class="nw-signal-name">Trading frequency</span>
                    <span style="color:{oc};font-size:13px;font-weight:600">
                      {tpm:.1f} trades / month</span>
                  </div>
                  <div class="nw-verdict">{ov}</div>
                </div>""", unsafe_allow_html=True)

        if len(buys) >= 2:
            sc = buys["stock"].value_counts()
            tp = sc.iloc[0] / len(buys) * 100
            cc = "#f87171" if tp > 40 else "#4ade80"
            cv = (f"{tp:.0f}% of trades in {sc.index[0]} — heavy concentration.") \
                 if tp > 40 else "Trades spread well across multiple assets."
            st.markdown(f"""<div class="nw-signal">
              <div class="nw-signal-header">
                <span class="nw-signal-name">Concentration check</span>
                <span style="color:{cc};font-size:13px;font-weight:600">
                  {tp:.0f}% in {sc.index[0]}</span>
              </div>
              <div class="nw-verdict">{cv}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Clear trade log"):
            st.session_state.trade_log = []
            st.rerun()
    else:
        st.info("Log at least 3 trades to unlock your behavioral analysis.")

# ════════════════════════════════════════════════════════
# PAGE: SECTOR HEATMAP
# ════════════════════════════════════════════════════════

elif page == "Sector Heatmap":
    st.markdown("## Market Heatmap")
    st.caption("Stocks, crypto and commodities — sector rotation at a glance")

    SECTORS = {
        "Banking":        ["HDFCBANK.NS","ICICIBANK.NS","KOTAKBANK.NS","AXISBANK.NS"],
        "IT":             ["TCS.NS","INFY.NS","WIPRO.NS","HCLTECH.NS"],
        "Energy":         ["RELIANCE.NS","ONGC.NS","BPCL.NS","IOC.NS"],
        "FMCG":           ["HINDUNILVR.NS","ITC.NS","NESTLEIND.NS"],
        "Auto":           ["MARUTI.NS","TATAMOTORS.NS","BAJAJ-AUTO.NS"],
        "Pharma":         ["SUNPHARMA.NS","DRREDDY.NS","CIPLA.NS"],
        "Metals":         ["TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS"],
        "Infrastructure": ["LT.NS","NTPC.NS","ADANIPORTS.NS"],
        "Consumer Tech":  ["ZOMATO.NS","NYKAA.NS","DMART.NS"],
        "US Tech":        ["AAPL","MSFT","GOOGL","NVDA"],
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
                    s1d.append( ((pn-hist['Close'].iloc[-2]) /hist['Close'].iloc[-2])*100)
                    s1w.append( ((pn-hist['Close'].iloc[-6]) /hist['Close'].iloc[-6])*100
                                if len(hist)>=6 else 0)
                    s1mo.append(((pn-hist['Close'].iloc[-22])/hist['Close'].iloc[-22])*100
                                if len(hist)>=22 else 0)
                except:
                    continue
            if s1d:
                results[sector] = {
                    "1d":  round(sum(s1d)/len(s1d),   2),
                    "1w":  round(sum(s1w)/len(s1w),   2),
                    "1mo": round(sum(s1mo)/len(s1mo), 2),
                }
        # add crypto via CoinGecko
        try:
            url  = "https://api.coingecko.com/api/v3/simple/price"
            resp = requests.get(url, params={
                "ids": "bitcoin,ethereum,solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }, timeout=10)
            data = resp.json()
            changes = [v.get("usd_24h_change",0) for v in data.values() if v]
            if changes:
                avg = round(sum(changes)/len(changes), 2)
                results["Crypto"] = {"1d": avg, "1w": avg*3, "1mo": avg*10}
        except:
            pass
        return results

    with st.spinner("Fetching market data..."):
        sector_data = get_sector_returns()

    if not sector_data:
        st.error("Could not fetch sector data.")
    else:
        timeframe = st.segmented_control("Timeframe",
            ["Today","This week","This month"], default="This week")
        tf_key = {"Today":"1d","This week":"1w","This month":"1mo"}[timeframe]

        st.markdown("<div class='nw-section'>Performance</div>",
                    unsafe_allow_html=True)
        sorted_sectors = sorted(sector_data.items(),
            key=lambda x: x[1][tf_key], reverse=True)
        max_abs = max(abs(v[tf_key]) for _,v in sorted_sectors) or 1

        cols = st.columns(2)
        for i, (sector, returns) in enumerate(sorted_sectors):
            ret       = returns[tf_key]
            sign      = "+" if ret >= 0 else ""
            intensity = min(abs(ret)/max_abs, 1.0)
            if ret >= 0:
                g=int(150+105*intensity); r=int(20+20*(1-intensity)); b=int(20+20*(1-intensity))
            else:
                r=int(150+105*intensity); g=int(20+20*(1-intensity)); b=int(20+20*(1-intensity))
            bg = f"rgb({r},{g},{b})"
            tc = "#0a0a0a" if intensity > 0.5 else "#f0f0f0"
            with cols[i%2]:
                st.markdown(f"""<div style="background:{bg};border-radius:12px;
                    padding:18px 20px;margin-bottom:10px">
                  <div style="font-size:13px;font-weight:600;color:{tc};margin-bottom:6px">
                    {sector}</div>
                  <div style="font-size:28px;font-weight:700;color:{tc};
                    letter-spacing:-1px;margin-bottom:10px">{sign}{ret:.2f}%</div>
                  <div style="display:flex;gap:12px;font-size:11px;color:{tc};opacity:0.75">
                    <span>1D {'+' if returns['1d']>=0 else ''}{returns['1d']:.2f}%</span>
                    <span>1W {'+' if returns['1w']>=0 else ''}{returns['1w']:.2f}%</span>
                    <span>1M {'+' if returns['1mo']>=0 else ''}{returns['1mo']:.2f}%</span>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Comparison chart</div>",
                    unsafe_allow_html=True)
        chart_df   = pd.DataFrame([{"Sector":s,"Return (%)":v[tf_key]}
                                    for s,v in sorted_sectors])
        colors_bar = ["#4ade80" if r>=0 else "#f87171"
                      for r in chart_df["Return (%)"]]
        fig_bar = go.Figure(go.Bar(
            x=chart_df["Return (%)"], y=chart_df["Sector"],
            orientation="h", marker_color=colors_bar,
            text=[f"{'+' if r>=0 else ''}{r:.2f}%" for r in chart_df["Return (%)"]],
            textposition="outside", textfont=dict(color="#888",size=12)))
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)', height=420,
            margin=dict(l=0,r=60,t=10,b=0),
            xaxis=dict(showgrid=True,gridcolor='#1a1a1a',color="#444",
                       zeroline=True,zerolinecolor="#333"),
            yaxis=dict(showgrid=False,color="#888"))
        st.plotly_chart(fig_bar, use_container_width=True)

# ════════════════════════════════════════════════════════
# PAGE: ALERTS
# ════════════════════════════════════════════════════════

elif page == "Alerts":
    st.markdown("## Smart Alerts")
    st.caption("Set compound conditions — get emailed when they trigger")

    if "alerts" not in st.session_state:
        st.session_state.alerts = []
    if "alert_log" not in st.session_state:
        st.session_state.alert_log = []

    st.markdown("<div class='nw-section'>Create an alert</div>",
                unsafe_allow_html=True)
    with st.expander("+ New alert",
                     expanded=len(st.session_state.alerts) == 0):
        ac1, ac2 = st.columns(2)
        with ac1:
            a_search  = st.text_input("Search asset",
                placeholder="e.g. Zomato, Bitcoin...", key="alert_search")
            a_results = search_assets(a_search)
            a_display = st.selectbox("Asset", list(a_results.keys()),
                key="alert_stock")
        with ac2:
            recipient_email = st.text_input("Send alert to",
                placeholder="you@gmail.com", key="alert_email")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Condition 1 — Price**")
        p1, p2 = st.columns(2)
        with p1:
            price_condition = st.selectbox("Price trigger",
                ["-- None --","Price rises above","Price drops below",
                 "Day change rises above %","Day change drops below %"],
                key="price_cond")
        with p2:
            price_value = st.number_input("Value", min_value=0.0,
                value=500.0, step=0.5, key="price_val")

        st.markdown("**Condition 2 — Volume (optional)**")
        volume_condition = st.selectbox("Volume trigger",
            ["-- None --","Volume is 2x average","Volume is 3x average"],
            key="vol_cond")

        st.markdown("**Condition 3 — RSI (optional)**")
        rsi_condition = st.selectbox("RSI signal",
            ["-- None --","RSI overbought (> 70)","RSI oversold (< 30)"],
            key="rsi_cond")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Create alert", use_container_width=True):
            if not recipient_email:
                st.warning("Enter a recipient email.")
            elif all(x == "-- None --" for x in
                     [price_condition, volume_condition, rsi_condition]):
                st.warning("Set at least one condition.")
            else:
                st.session_state.alerts.append({
                    "name":       a_display,
                    "recipient":  recipient_email,
                    "price_cond": price_condition,
                    "price_val":  price_value,
                    "vol_cond":   volume_condition,
                    "rsi_cond":   rsi_condition,
                    "active":     True,
                    "created":    datetime.now().strftime("%d %b %Y"),
                })
                st.success(f"Alert created for {a_display}")
                st.rerun()

    if st.session_state.alerts:
        st.markdown("<div class='nw-section'>Active alerts</div>",
                    unsafe_allow_html=True)
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
            c1,c2,c3 = st.columns([3,4,1])
            c1.markdown(f"**{alert['name']}**")
            c2.markdown(
                f"<span style='color:#555;font-size:12px'>"
                f"{' AND '.join(conditions)}</span>",
                unsafe_allow_html=True)
            with c3:
                if st.button("Remove", key=f"del_{i}"):
                    st.session_state.alerts[i]["active"] = False
                    st.rerun()
            st.markdown(
                "<hr style='margin:6px 0;border:none;border-top:1px solid #1a1a1a'>",
                unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Check & send</div>",
                    unsafe_allow_html=True)
        st.caption("Background thread checks every 60 seconds automatically")
        if st.button("Check now", use_container_width=True):
            triggered = 0
            for alert in st.session_state.alerts:
                if not alert["active"]:
                    continue
                try:
                    cp = get_current_price(alert["name"])
                    if not cp:
                        continue
                    hist, _ = load_history(alert["name"], "1mo")
                    if hist.empty or len(hist) < 2:
                        continue
                    prev    = hist['Close'].iloc[-2]
                    day_chg = ((cp - prev) / prev) * 100
                    avg_vol = hist['Volume'].mean() if 'Volume' in hist else 0
                    cur_vol = hist['Volume'].iloc[-1] if 'Volume' in hist else 0
                    rsi_v   = compute_rsi(hist['Close'])
                    cur_rsi = rsi_v.iloc[-1] if not rsi_v.empty else 50

                    conditions_met = []
                    pc = alert["price_cond"]
                    pv = alert["price_val"]
                    if pc == "Price rises above" and cp > pv:
                        conditions_met.append(f"Price {cp:,.2f} > {pv:,.2f}")
                    elif pc == "Price drops below" and cp < pv:
                        conditions_met.append(f"Price {cp:,.2f} < {pv:,.2f}")
                    elif pc == "Day change rises above %" and day_chg > pv:
                        conditions_met.append(f"Change {day_chg:+.2f}% > +{pv:.1f}%")
                    elif pc == "Day change drops below %" and day_chg < -pv:
                        conditions_met.append(f"Change {day_chg:+.2f}% < -{pv:.1f}%")
                    vc = alert["vol_cond"]
                    if vc == "Volume is 2x average" and avg_vol>0 and cur_vol>avg_vol*2:
                        conditions_met.append("Volume 2x avg")
                    elif vc == "Volume is 3x average" and avg_vol>0 and cur_vol>avg_vol*3:
                        conditions_met.append("Volume 3x avg")
                    rc = alert["rsi_cond"]
                    if rc == "RSI overbought (> 70)" and cur_rsi > 70:
                        conditions_met.append(f"RSI {cur_rsi:.1f} overbought")
                    elif rc == "RSI oversold (< 30)" and cur_rsi < 30:
                        conditions_met.append(f"RSI {cur_rsi:.1f} oversold")

                    total = sum([1 for x in [alert["price_cond"],
                        alert["vol_cond"],alert["rsi_cond"]]
                        if x != "-- None --"])
                    if len(conditions_met) == total and total > 0:
                        sent = send_alert_email(alert["recipient"],
                            alert["name"]," · ".join(conditions_met),cp,day_chg)
                        if sent:
                            triggered += 1
                            st.session_state.alert_log.append({
                                "stock":   alert["name"],
                                "trigger": " · ".join(conditions_met),
                                "time":    datetime.now().strftime("%d %b %Y · %I:%M %p"),
                                "sent_to": alert["recipient"],
                            })
                except:
                    continue
            if triggered > 0:
                st.success(f"{triggered} alert(s) triggered — emails sent.")
            else:
                st.info("No alerts triggered right now.")

        if st.session_state.alert_log:
            st.markdown("<div class='nw-section'>Alert history</div>",
                        unsafe_allow_html=True)
            for log in reversed(st.session_state.alert_log[-10:]):
                st.markdown(
                    f"<span style='color:#f0f0f0;font-size:13px'>"
                    f"<b>{log['stock']}</b> — {log['trigger']}</span>"
                    f"<br><span style='color:#444;font-size:11px'>"
                    f"{log['time']} · {log['sent_to']}</span>",
                    unsafe_allow_html=True)
                st.markdown(
                    "<hr style='margin:8px 0;border:none;"
                    "border-top:1px solid #1a1a1a'>",
                    unsafe_allow_html=True)
    else:
        st.info("No alerts yet — create your first one above.")

# ════════════════════════════════════════════════════════
# PAGE: REPORT CARD
# ════════════════════════════════════════════════════════

elif page == "Report Card":
    st.markdown("## Monthly Report Card")
    st.caption("Your portfolio performance — generated and ready to share")

    if not st.session_state.get("holdings"):
        st.info("Add assets to your portfolio first.")
    else:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph,
            Spacer, Table, TableStyle, HRFlowable)
        from reportlab.lib.styles import ParagraphStyle
        import io

        rows           = []
        total_invested = 0
        total_current  = 0

        for h in st.session_state.holdings:
            cp = get_current_price(h["Name"])
            if not cp:
                continue
            invested = h["Qty"] * h["Buy Price"]
            cur_val  = h["Qty"] * cp
            pnl      = cur_val - invested
            pnl_pct  = (pnl / invested) * 100
            rows.append({
                "name": h["Name"], "type": h["Type"],
                "qty": h["Qty"], "buy_price": h["Buy Price"],
                "cur_price": cp, "invested": invested,
                "cur_val": cur_val, "pnl": pnl, "pnl_pct": pnl_pct,
            })
            total_invested += invested
            total_current  += cur_val

        total_pnl     = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
        nifty_return  = get_nifty_return()
        best          = max(rows, key=lambda x: x["pnl_pct"]) if rows else None
        worst         = min(rows, key=lambda x: x["pnl_pct"]) if rows else None

        st.markdown("<div class='nw-section'>Summary</div>",
                    unsafe_allow_html=True)
        m1,m2,m3,m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Invested</div>
              <div class="nw-metric-value">{total_invested:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Current value</div>
              <div class="nw-metric-value">{total_current:,.2f}</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            dc = "nw-metric-delta-up" if total_pnl>=0 else "nw-metric-delta-down"
            sg = "+" if total_pnl>=0 else ""
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">Total P&L</div>
              <div class="nw-metric-value">{sg}{total_pnl:,.2f}</div>
              <div class="{dc}">{sg}{total_pnl_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            nc = "nw-metric-delta-up" if total_pnl_pct>=nifty_return \
                 else "nw-metric-delta-down"
            st.markdown(f"""<div class="nw-metric">
              <div class="nw-metric-label">vs Nifty 50</div>
              <div class="nw-metric-value">
                {'+' if nifty_return>=0 else ''}{nifty_return:.2f}%</div>
              <div class="{nc}">You: {sg}{total_pnl_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)

        if best and worst:
            st.markdown("<div class='nw-section'>Best & worst</div>",
                        unsafe_allow_html=True)
            b1,b2 = st.columns(2)
            with b1:
                st.markdown(f"""<div class="nw-metric">
                  <div class="nw-metric-label">Best holding</div>
                  <div class="nw-metric-value" style="color:#4ade80">
                    {best['name']}</div>
                  <div class="nw-metric-delta-up">
                    +{best['pnl_pct']:.2f}%</div>
                </div>""", unsafe_allow_html=True)
            with b2:
                wc = "nw-metric-delta-up" if worst['pnl']>=0 \
                     else "nw-metric-delta-down"
                ws = "+" if worst['pnl']>=0 else ""
                st.markdown(f"""<div class="nw-metric">
                  <div class="nw-metric-label">Worst holding</div>
                  <div class="nw-metric-value" style="color:#f87171">
                    {worst['name']}</div>
                  <div class="{wc}">{ws}{worst['pnl_pct']:.2f}%</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div class='nw-section'>Download</div>",
                    unsafe_allow_html=True)
        if st.button("Generate PDF report card", use_container_width=True):
            buffer = io.BytesIO()
            doc    = SimpleDocTemplate(buffer, pagesize=A4,
                leftMargin=20*mm, rightMargin=20*mm,
                topMargin=20*mm, bottomMargin=20*mm)
            BLACK = colors.HexColor("#0a0a0a")
            GREY  = colors.HexColor("#888888")
            ts    = ParagraphStyle("t", fontSize=28, textColor=BLACK,
                fontName="Helvetica-Bold", spaceAfter=4, leading=32)
            ss    = ParagraphStyle("s", fontSize=11, textColor=GREY,
                fontName="Helvetica", spaceAfter=20)
            sec   = ParagraphStyle("sec", fontSize=9, textColor=GREY,
                fontName="Helvetica-Bold", spaceBefore=20, spaceAfter=8)
            body  = ParagraphStyle("b", fontSize=11, textColor=BLACK,
                fontName="Helvetica", spaceAfter=6, leading=16)

            story = [
                Paragraph("Voltr", ts),
                Paragraph(f"Portfolio Report · {datetime.now().strftime('%B %Y')}", ss),
                HRFlowable(width="100%", thickness=0.5,
                    color=colors.HexColor("#e0e0e0"), spaceAfter=16),
                Paragraph("Portfolio Summary", sec),
            ]

            sg    = "+" if total_pnl>=0 else ""
            ng    = "+" if nifty_return>=0 else ""
            beat  = "Outperformed" if total_pnl_pct>=nifty_return \
                    else "Underperformed"
            sdata = [
                ["Metric","Value"],
                ["Total invested",  f"{total_invested:,.2f}"],
                ["Current value",   f"{total_current:,.2f}"],
                ["Total P&L",       f"{sg}{total_pnl:,.2f} ({sg}{total_pnl_pct:.2f}%)"],
                ["Nifty 50 return", f"{ng}{nifty_return:.2f}%"],
                ["vs Benchmark",    f"{beat} by {abs(total_pnl_pct-nifty_return):.2f}%"],
                ["Holdings",        str(len(rows))],
            ]
            t1 = Table(sdata, colWidths=[80*mm,90*mm])
            t1.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f5f5f5")),
                ("TEXTCOLOR",(0,0),(-1,0),GREY),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,0),8),
                ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",(0,1),(-1,-1),10),
                ("TEXTCOLOR",(0,1),(-1,-1),BLACK),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),
                 [colors.white,colors.HexColor("#fafafa")]),
                ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#e0e0e0")),
                ("LEFTPADDING",(0,0),(-1,-1),10),
                ("RIGHTPADDING",(0,0),(-1,-1),10),
                ("TOPPADDING",(0,0),(-1,-1),8),
                ("BOTTOMPADDING",(0,0),(-1,-1),8),
            ]))
            story.append(t1)
            story.append(Paragraph("Holdings", sec))
            hdata = [["Asset","Type","Qty","Buy","Current","P&L","P&L %"]]
            for r in sorted(rows,key=lambda x:x["pnl_pct"],reverse=True):
                ps = "+" if r["pnl"]>=0 else ""
                hdata.append([r["name"],r["type"],f"{r['qty']:.4f}",
                    f"{r['buy_price']:,.2f}",f"{r['cur_price']:,.2f}",
                    f"{ps}{r['pnl']:,.2f}",f"{ps}{r['pnl_pct']:.2f}%"])
            t2 = Table(hdata,colWidths=[40*mm,15*mm,15*mm,25*mm,25*mm,25*mm,20*mm])
            t2.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f5f5f5")),
                ("TEXTCOLOR",(0,0),(-1,0),GREY),
                ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("FONTSIZE",(0,0),(-1,0),7),
                ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
                ("FONTSIZE",(0,1),(-1,-1),8),
                ("TEXTCOLOR",(0,1),(-1,-1),BLACK),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),
                 [colors.white,colors.HexColor("#fafafa")]),
                ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#e0e0e0")),
                ("LEFTPADDING",(0,0),(-1,-1),6),
                ("RIGHTPADDING",(0,0),(-1,-1),6),
                ("TOPPADDING",(0,0),(-1,-1),6),
                ("BOTTOMPADDING",(0,0),(-1,-1),6),
            ]))
            story.append(t2)
            story.append(Spacer(1,20*mm))
            story.append(HRFlowable(width="100%",thickness=0.5,
                color=colors.HexColor("#e0e0e0"),spaceAfter=8))
            story.append(Paragraph(
                f"Generated by Voltr · {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
                ParagraphStyle("f",fontSize=9,textColor=GREY,fontName="Helvetica")))
            doc.build(story)
            buffer.seek(0)
            st.download_button(label="Download PDF", data=buffer,
                file_name=f"voltr_report_{datetime.now().strftime('%B_%Y').lower()}.pdf",
                mime="application/pdf", use_container_width=True)
            st.success("Report generated. Click Download PDF above.")

# ════════════════════════════════════════════════════════
# PAGE: MARKET SIGNALS
# ════════════════════════════════════════════════════════

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
