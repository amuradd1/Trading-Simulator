"""
Portfolio Trading Simulator — Backend Server
Uses yfinance for robust market data, Flask for API + static serving.
"""

import json
import os
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ============================================================
# Asset Universe — ESG screened, no defense/weapons stocks
# ============================================================
ASSET_UNIVERSE = {
    # US Large Cap Tech
    "AAPL":  {"name": "Apple",              "sector": "Tech",               "category": "US Large Cap"},
    "MSFT":  {"name": "Microsoft",          "sector": "Tech",               "category": "US Large Cap"},
    "NVDA":  {"name": "NVIDIA",             "sector": "Semiconductors",     "category": "US Large Cap"},
    "AMZN":  {"name": "Amazon",             "sector": "Consumer/Cloud",     "category": "US Large Cap"},
    "GOOGL": {"name": "Alphabet",           "sector": "Tech",               "category": "US Large Cap"},
    "META":  {"name": "Meta Platforms",     "sector": "Tech",               "category": "US Large Cap"},
    "TSLA":  {"name": "Tesla",              "sector": "EV/Energy",          "category": "US Large Cap"},
    # US Broader
    "SPY":   {"name": "S&P 500 ETF",        "sector": "Index",              "category": "US Index"},
    "QQQ":   {"name": "Nasdaq 100 ETF",     "sector": "Index",              "category": "US Index"},
    "IWM":   {"name": "Russell 2000 ETF",   "sector": "Small Cap",          "category": "US Index"},
    # Healthcare / Consumer
    "JNJ":   {"name": "Johnson & Johnson",  "sector": "Healthcare",         "category": "US Large Cap"},
    "UNH":   {"name": "UnitedHealth",       "sector": "Healthcare",         "category": "US Large Cap"},
    "V":     {"name": "Visa",               "sector": "Financials",         "category": "US Large Cap"},
    "JPM":   {"name": "JPMorgan Chase",     "sector": "Financials",         "category": "US Large Cap"},
    # International / Emerging Markets
    "EEM":   {"name": "Emerging Markets ETF", "sector": "EM Equity",        "category": "Emerging Markets"},
    "VWO":   {"name": "Vanguard EM ETF",    "sector": "EM Equity",          "category": "Emerging Markets"},
    "EFA":   {"name": "Intl Developed ETF", "sector": "Intl Developed",     "category": "International"},
    "VEA":   {"name": "Vanguard Intl ETF",  "sector": "Intl Developed",     "category": "International"},
    "FXI":   {"name": "China Large Cap ETF", "sector": "China Equity",      "category": "Emerging Markets"},
    "EWZ":   {"name": "Brazil ETF",         "sector": "LatAm Equity",       "category": "Emerging Markets"},
    "INDA":  {"name": "India ETF",          "sector": "India Equity",       "category": "Emerging Markets"},
    # Commodities
    "GLD":   {"name": "Gold ETF",           "sector": "Precious Metals",    "category": "Commodities"},
    "SLV":   {"name": "Silver ETF",         "sector": "Precious Metals",    "category": "Commodities"},
    "USO":   {"name": "Oil ETF",            "sector": "Energy Commodity",   "category": "Commodities"},
    "DBA":   {"name": "Agriculture ETF",    "sector": "Agriculture",        "category": "Commodities"},
    # Fixed Income
    "TLT":   {"name": "20+ Year Treasury",  "sector": "Long Bonds",         "category": "Fixed Income"},
    "BND":   {"name": "Total Bond Market",  "sector": "Bonds",              "category": "Fixed Income"},
    "HYG":   {"name": "High Yield Corp",    "sector": "Credit",             "category": "Fixed Income"},
    # ESG / Clean Energy
    "ICLN":  {"name": "Clean Energy ETF",   "sector": "Clean Energy",       "category": "ESG"},
    "TAN":   {"name": "Solar ETF",          "sector": "Solar",              "category": "ESG"},
    # REITs
    "VNQ":   {"name": "Real Estate ETF",    "sector": "REITs",              "category": "Real Estate"},
    # Crypto proxy
    "BITO":  {"name": "Bitcoin Strategy ETF", "sector": "Crypto",           "category": "Crypto"},
}

# Defense exclusion list (for validation)
EXCLUDED_TICKERS = {
    "LMT", "RTX", "NOC", "BA", "GD", "HII", "LHX", "LDOS",
    "PLTR", "BWXT", "KTOS", "AVAV", "HEI", "TDG",
}


def _get_cache_key():
    """Cache key changes every 15 minutes to balance freshness and rate limits."""
    now = datetime.utcnow()
    return f"{now.strftime('%Y-%m-%d-%H')}-{now.minute // 15}"


@lru_cache(maxsize=64)
def fetch_price_history(ticker, period, interval, _cache_key=None):
    """Fetch price history from Yahoo Finance with caching."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        if df.empty:
            return None
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


# ============================================================
# API Routes
# ============================================================

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/universe")
def get_universe():
    """Return the full investable asset universe."""
    result = []
    for ticker, info in ASSET_UNIVERSE.items():
        result.append({"ticker": ticker, **info})
    return jsonify(result)


@app.route("/api/prices")
def get_prices():
    """
    Fetch historical prices for given tickers.
    Query params:
      tickers: comma-separated list (e.g. AAPL,MSFT,SPY)
      period:  yfinance period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y)
      interval: yfinance interval string (1m, 5m, 15m, 1h, 1d, 1wk)
    """
    tickers = request.args.get("tickers", "SPY").split(",")
    period = request.args.get("period", "1mo")
    interval = request.args.get("interval", "1d")

    # Validate tickers
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    tickers = [t for t in tickers if t not in EXCLUDED_TICKERS]

    cache_key = _get_cache_key()
    result = {}

    for ticker in tickers:
        df = fetch_price_history(ticker, period, interval, cache_key)
        if df is not None and not df.empty:
            result[ticker] = {
                "timestamps": [ts.isoformat() for ts in df.index],
                "open": df["Open"].round(4).tolist(),
                "high": df["High"].round(4).tolist(),
                "low": df["Low"].round(4).tolist(),
                "close": df["Close"].round(4).tolist(),
                "volume": df["Volume"].tolist(),
            }

    return jsonify(result)


@app.route("/api/quotes")
def get_quotes():
    """Get latest quote for tickers."""
    tickers = request.args.get("tickers", "SPY").split(",")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    tickers = [t for t in tickers if t not in EXCLUDED_TICKERS]

    result = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            result[ticker] = {
                "price": round(float(info.last_price), 2) if hasattr(info, 'last_price') else None,
                "previousClose": round(float(info.previous_close), 2) if hasattr(info, 'previous_close') else None,
                "marketCap": int(info.market_cap) if hasattr(info, 'market_cap') and info.market_cap else None,
            }
        except Exception as e:
            print(f"Quote error for {ticker}: {e}")
            result[ticker] = {"price": None, "error": str(e)}

    return jsonify(result)


@app.route("/api/macro")
def get_macro():
    """
    Compute macro indicators from real market data.
    Uses SPY, TLT, GLD, EEM, VIX proxy, DXY proxy.
    """
    cache_key = _get_cache_key()
    indicators = {}

    # SPY for market trend
    spy = fetch_price_history("SPY", "3mo", "1d", cache_key)
    if spy is not None and len(spy) > 1:
        spy_now = spy["Close"].iloc[-1]
        spy_1m = spy["Close"].iloc[-min(21, len(spy))]
        spy_3m = spy["Close"].iloc[0]
        indicators["spy"] = {
            "current": round(float(spy_now), 2),
            "change_1m": round(float((spy_now - spy_1m) / spy_1m * 100), 2),
            "change_3m": round(float((spy_now - spy_3m) / spy_3m * 100), 2),
            "trend": "Bullish" if spy_now > spy_1m else "Bearish",
        }

    # TLT for rates
    tlt = fetch_price_history("TLT", "3mo", "1d", cache_key)
    if tlt is not None and len(tlt) > 1:
        tlt_now = tlt["Close"].iloc[-1]
        tlt_1m = tlt["Close"].iloc[-min(21, len(tlt))]
        indicators["bonds"] = {
            "current": round(float(tlt_now), 2),
            "change_1m": round(float((tlt_now - tlt_1m) / tlt_1m * 100), 2),
            "signal": "Rates Falling" if tlt_now > tlt_1m else "Rates Rising",
        }

    # GLD for safe haven
    gld = fetch_price_history("GLD", "3mo", "1d", cache_key)
    if gld is not None and len(gld) > 1:
        gld_now = gld["Close"].iloc[-1]
        gld_1m = gld["Close"].iloc[-min(21, len(gld))]
        indicators["gold"] = {
            "current": round(float(gld_now), 2),
            "change_1m": round(float((gld_now - gld_1m) / gld_1m * 100), 2),
            "demand": "Elevated" if gld_now > gld_1m * 1.02 else "Normal",
        }

    # EEM for EM sentiment
    eem = fetch_price_history("EEM", "3mo", "1d", cache_key)
    if eem is not None and len(eem) > 1:
        eem_now = eem["Close"].iloc[-1]
        eem_1m = eem["Close"].iloc[-min(21, len(eem))]
        indicators["em"] = {
            "current": round(float(eem_now), 2),
            "change_1m": round(float((eem_now - eem_1m) / eem_1m * 100), 2),
            "trend": "Risk-On" if eem_now > eem_1m else "Risk-Off",
        }

    # VIX for volatility
    vix = fetch_price_history("^VIX", "3mo", "1d", cache_key)
    if vix is not None and len(vix) > 1:
        vix_now = vix["Close"].iloc[-1]
        indicators["vix"] = {
            "current": round(float(vix_now), 2),
            "regime": "Low Vol" if vix_now < 15 else "Moderate" if vix_now < 25 else "High Vol",
        }

    # USO for oil
    uso = fetch_price_history("USO", "3mo", "1d", cache_key)
    if uso is not None and len(uso) > 1:
        uso_now = uso["Close"].iloc[-1]
        uso_1m = uso["Close"].iloc[-min(21, len(uso))]
        indicators["oil"] = {
            "current": round(float(uso_now), 2),
            "change_1m": round(float((uso_now - uso_1m) / uso_1m * 100), 2),
        }

    # Overall regime
    spy_trend = indicators.get("spy", {}).get("change_1m", 0)
    vix_level = indicators.get("vix", {}).get("current", 20)
    if spy_trend > 2 and vix_level < 20:
        regime = "Risk-On"
    elif spy_trend < -2 or vix_level > 25:
        regime = "Risk-Off"
    else:
        regime = "Neutral"

    indicators["regime"] = regime

    return jsonify(indicators)


@app.route("/api/validate_ticker")
def validate_ticker():
    """Check if a ticker is valid and not excluded."""
    ticker = request.args.get("ticker", "").strip().upper()
    if ticker in EXCLUDED_TICKERS:
        return jsonify({"valid": False, "reason": "Excluded: defense/weapons sector"})
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        if hasattr(info, 'last_price') and info.last_price:
            return jsonify({"valid": True, "price": round(float(info.last_price), 2)})
        return jsonify({"valid": False, "reason": "No price data available"})
    except Exception:
        return jsonify({"valid": False, "reason": "Ticker not found"})


# ============================================================
# Serve static files
# ============================================================

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Portfolio Trading Simulator")
    print(f"  Running on http://localhost:{port}")
    print(f"  Asset universe: {len(ASSET_UNIVERSE)} instruments")
    print(f"  Excluded (defense): {len(EXCLUDED_TICKERS)} tickers\n")
    app.run(host="0.0.0.0", port=port, debug=True)
