"""
Portfolio Trading Simulator — Backend Server
Dual mode: Live data via yfinance when available, realistic simulation fallback.
"""

import json
import math
import os
import random
import time
from datetime import datetime, timedelta
from functools import lru_cache

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ============================================================
# Asset Universe — ESG screened, no defense/weapons stocks
# ============================================================
ASSET_UNIVERSE = {
    "AAPL":  {"name": "Apple",              "sector": "Tech",               "category": "US Large Cap",      "basePrice": 195.50, "annualVol": 0.28, "annualReturn": 0.12},
    "MSFT":  {"name": "Microsoft",          "sector": "Tech",               "category": "US Large Cap",      "basePrice": 425.00, "annualVol": 0.26, "annualReturn": 0.10},
    "NVDA":  {"name": "NVIDIA",             "sector": "Semiconductors",     "category": "US Large Cap",      "basePrice": 895.00, "annualVol": 0.48, "annualReturn": 0.20},
    "AMZN":  {"name": "Amazon",             "sector": "Consumer/Cloud",     "category": "US Large Cap",      "basePrice": 188.00, "annualVol": 0.30, "annualReturn": 0.11},
    "GOOGL": {"name": "Alphabet",           "sector": "Tech",               "category": "US Large Cap",      "basePrice": 158.00, "annualVol": 0.28, "annualReturn": 0.09},
    "META":  {"name": "Meta Platforms",     "sector": "Tech",               "category": "US Large Cap",      "basePrice": 515.00, "annualVol": 0.35, "annualReturn": 0.14},
    "TSLA":  {"name": "Tesla",              "sector": "EV/Energy",          "category": "US Large Cap",      "basePrice": 178.00, "annualVol": 0.55, "annualReturn": 0.08},
    "SPY":   {"name": "S&P 500 ETF",        "sector": "Index",              "category": "US Index",          "basePrice": 528.00, "annualVol": 0.14, "annualReturn": 0.09},
    "QQQ":   {"name": "Nasdaq 100 ETF",     "sector": "Index",              "category": "US Index",          "basePrice": 448.00, "annualVol": 0.18, "annualReturn": 0.11},
    "IWM":   {"name": "Russell 2000 ETF",   "sector": "Small Cap",          "category": "US Index",          "basePrice": 205.00, "annualVol": 0.20, "annualReturn": 0.07},
    "JNJ":   {"name": "Johnson & Johnson",  "sector": "Healthcare",         "category": "US Large Cap",      "basePrice": 155.00, "annualVol": 0.16, "annualReturn": 0.05},
    "UNH":   {"name": "UnitedHealth",       "sector": "Healthcare",         "category": "US Large Cap",      "basePrice": 520.00, "annualVol": 0.22, "annualReturn": 0.08},
    "V":     {"name": "Visa",               "sector": "Financials",         "category": "US Large Cap",      "basePrice": 285.00, "annualVol": 0.20, "annualReturn": 0.10},
    "JPM":   {"name": "JPMorgan Chase",     "sector": "Financials",         "category": "US Large Cap",      "basePrice": 198.00, "annualVol": 0.24, "annualReturn": 0.09},
    "EEM":   {"name": "Emerging Markets ETF","sector": "EM Equity",          "category": "Emerging Markets",  "basePrice": 42.50,  "annualVol": 0.20, "annualReturn": 0.06},
    "VWO":   {"name": "Vanguard EM ETF",    "sector": "EM Equity",          "category": "Emerging Markets",  "basePrice": 43.00,  "annualVol": 0.19, "annualReturn": 0.06},
    "EFA":   {"name": "Intl Developed ETF", "sector": "Intl Developed",     "category": "International",     "basePrice": 79.00,  "annualVol": 0.15, "annualReturn": 0.05},
    "VEA":   {"name": "Vanguard Intl ETF",  "sector": "Intl Developed",     "category": "International",     "basePrice": 50.50,  "annualVol": 0.15, "annualReturn": 0.05},
    "FXI":   {"name": "China Large Cap ETF","sector": "China Equity",       "category": "Emerging Markets",  "basePrice": 28.00,  "annualVol": 0.28, "annualReturn": 0.04},
    "EWZ":   {"name": "Brazil ETF",         "sector": "LatAm Equity",       "category": "Emerging Markets",  "basePrice": 32.00,  "annualVol": 0.30, "annualReturn": 0.05},
    "INDA":  {"name": "India ETF",          "sector": "India Equity",       "category": "Emerging Markets",  "basePrice": 52.00,  "annualVol": 0.22, "annualReturn": 0.08},
    "GLD":   {"name": "Gold ETF",           "sector": "Precious Metals",    "category": "Commodities",       "basePrice": 200.00, "annualVol": 0.14, "annualReturn": 0.06},
    "SLV":   {"name": "Silver ETF",         "sector": "Precious Metals",    "category": "Commodities",       "basePrice": 23.00,  "annualVol": 0.25, "annualReturn": 0.04},
    "USO":   {"name": "Oil ETF",            "sector": "Energy Commodity",   "category": "Commodities",       "basePrice": 76.00,  "annualVol": 0.30, "annualReturn": 0.03},
    "DBA":   {"name": "Agriculture ETF",    "sector": "Agriculture",        "category": "Commodities",       "basePrice": 24.50,  "annualVol": 0.15, "annualReturn": 0.02},
    "TLT":   {"name": "20+ Year Treasury",  "sector": "Long Bonds",         "category": "Fixed Income",      "basePrice": 92.00,  "annualVol": 0.16, "annualReturn": 0.03},
    "BND":   {"name": "Total Bond Market",  "sector": "Bonds",              "category": "Fixed Income",      "basePrice": 73.00,  "annualVol": 0.06, "annualReturn": 0.035},
    "HYG":   {"name": "High Yield Corp",    "sector": "Credit",             "category": "Fixed Income",      "basePrice": 77.00,  "annualVol": 0.08, "annualReturn": 0.05},
    "ICLN":  {"name": "Clean Energy ETF",   "sector": "Clean Energy",       "category": "ESG",               "basePrice": 14.50,  "annualVol": 0.32, "annualReturn": 0.06},
    "TAN":   {"name": "Solar ETF",          "sector": "Solar",              "category": "ESG",               "basePrice": 42.00,  "annualVol": 0.38, "annualReturn": 0.07},
    "VNQ":   {"name": "Real Estate ETF",    "sector": "REITs",              "category": "Real Estate",       "basePrice": 85.00,  "annualVol": 0.18, "annualReturn": 0.05},
    "BITO":  {"name": "Bitcoin Strategy ETF","sector": "Crypto",            "category": "Crypto",            "basePrice": 28.00,  "annualVol": 0.60, "annualReturn": 0.15},
}

EXCLUDED_TICKERS = {
    "LMT", "RTX", "NOC", "BA", "GD", "HII", "LHX", "LDOS",
    "PLTR", "BWXT", "KTOS", "AVAV", "HEI", "TDG",
}

# Correlation groups for realistic co-movement
CORRELATION_GROUPS = {
    "US Tech": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "QQQ"],
    "US Broad": ["SPY", "IWM", "V", "JPM"],
    "Healthcare": ["JNJ", "UNH"],
    "EM": ["EEM", "VWO", "FXI", "EWZ", "INDA"],
    "Intl Dev": ["EFA", "VEA"],
    "Commodities": ["GLD", "SLV", "USO", "DBA"],
    "Bonds": ["TLT", "BND", "HYG"],
    "Alt": ["TSLA", "ICLN", "TAN", "VNQ", "BITO"],
}

# ============================================================
# Simulation Engine (fallback when yfinance unavailable)
# ============================================================
_sim_seed = int(time.time() // 86400)  # changes daily
_sim_cache = {}

def _seeded_random(seed):
    """Simple deterministic RNG."""
    rng = random.Random(seed)
    return rng

def _generate_correlated_returns(rng, n_periods, dt):
    """Generate correlated returns for all assets using group correlation."""
    tickers = list(ASSET_UNIVERSE.keys())
    n = len(tickers)

    # Build group factor returns
    group_factors = {}
    for gname in CORRELATION_GROUPS:
        group_factors[gname] = [rng.gauss(0, 1) for _ in range(n_periods)]

    # Market factor
    market_factor = [rng.gauss(0, 1) for _ in range(n_periods)]

    # Assign each ticker to its group
    ticker_group = {}
    for gname, members in CORRELATION_GROUPS.items():
        for t in members:
            ticker_group[t] = gname

    all_returns = {}
    for ticker in tickers:
        asset = ASSET_UNIVERSE[ticker]
        vol = asset["annualVol"]
        drift = asset["annualReturn"]
        group = ticker_group.get(ticker)

        returns = []
        for p in range(n_periods):
            # 40% market, 30% group, 30% idiosyncratic
            mkt = market_factor[p]
            grp = group_factors.get(group, market_factor)[p] if group else mkt
            idio = rng.gauss(0, 1)
            z = 0.4 * mkt + 0.3 * grp + 0.3 * idio

            r = (drift - 0.5 * vol ** 2) * dt + vol * math.sqrt(dt) * z
            returns.append(r)
        all_returns[ticker] = returns

    return all_returns


def _generate_price_history(period, interval):
    """Generate simulated price history matching yfinance output format."""
    cache_key = f"{period}_{interval}_{_sim_seed}"
    if cache_key in _sim_cache:
        return _sim_cache[cache_key]

    now = datetime.utcnow().replace(second=0, microsecond=0)

    # Map period/interval to number of data points and step size
    period_map = {
        "1d":  (24 * 12, timedelta(minutes=5)),     # 5min bars for 1 day
        "2d":  (48 * 4, timedelta(minutes=15)),      # 15min bars for 2 days
        "5d":  (5 * 7, timedelta(hours=1)),           # hourly for 5 days
        "1mo": (21, timedelta(days=1)),               # daily for 1 month
        "3mo": (63, timedelta(days=1)),               # daily for 3 months
        "6mo": (126, timedelta(days=1)),              # daily for 6 months
        "1y":  (252, timedelta(days=1)),              # daily for 1 year
        "ytd": (None, timedelta(days=1)),             # daily from Jan 1
    }

    if period == "ytd":
        jan1 = datetime(now.year, 1, 1)
        n_periods = (now - jan1).days
        step = timedelta(days=1)
    else:
        n_periods, step = period_map.get(period, (252, timedelta(days=1)))

    if n_periods is None or n_periods < 1:
        n_periods = 21

    # Calculate dt in years
    if step >= timedelta(days=1):
        dt = step.days / 365.0
    else:
        dt = step.total_seconds() / (365.25 * 24 * 3600)

    rng = _seeded_random(_sim_seed + hash(period))
    all_returns = _generate_correlated_returns(rng, n_periods, dt)

    result = {}
    for ticker in ASSET_UNIVERSE:
        asset = ASSET_UNIVERSE[ticker]
        base = asset["basePrice"]

        timestamps = []
        opens, highs, lows, closes, volumes = [], [], [], [], []

        price = base
        for i in range(n_periods):
            ts = now - (n_periods - i) * step
            # Skip weekends for daily data
            if step >= timedelta(days=1) and ts.weekday() >= 5:
                continue

            r = all_returns[ticker][i]
            open_p = price
            close_p = price * math.exp(r)

            # Intraday high/low noise
            spread = abs(close_p - open_p) + price * asset["annualVol"] * math.sqrt(dt) * 0.3
            high_p = max(open_p, close_p) + abs(rng.gauss(0, spread * 0.3))
            low_p = min(open_p, close_p) - abs(rng.gauss(0, spread * 0.3))
            low_p = max(low_p, 0.01)

            vol = int(rng.gauss(5_000_000, 2_000_000) * (base / 100))
            vol = max(vol, 100_000)

            timestamps.append(ts.isoformat())
            opens.append(round(open_p, 4))
            highs.append(round(high_p, 4))
            lows.append(round(low_p, 4))
            closes.append(round(close_p, 4))
            volumes.append(vol)

            price = close_p

        result[ticker] = {
            "timestamps": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }

    _sim_cache[cache_key] = result
    return result


def _try_yfinance(tickers, period, interval):
    """Try fetching from yfinance, return None on failure."""
    try:
        import yfinance as yf
        result = {}
        for ticker in tickers:
            t = yf.Ticker(ticker)
            df = t.history(period=period, interval=interval)
            if df is not None and not df.empty:
                df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
                result[ticker] = {
                    "timestamps": [ts.isoformat() for ts in df.index],
                    "open": df["Open"].round(4).tolist(),
                    "high": df["High"].round(4).tolist(),
                    "low": df["Low"].round(4).tolist(),
                    "close": df["Close"].round(4).tolist(),
                    "volume": df["Volume"].tolist(),
                }
        if result:
            return result
    except Exception as e:
        print(f"yfinance unavailable: {e}")
    return None


# ============================================================
# API Routes
# ============================================================

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/universe")
def get_universe():
    result = []
    for ticker, info in ASSET_UNIVERSE.items():
        result.append({"ticker": ticker, "name": info["name"], "sector": info["sector"],
                        "category": info["category"]})
    return jsonify(result)


@app.route("/api/prices")
def get_prices():
    tickers = request.args.get("tickers", "SPY").split(",")
    period = request.args.get("period", "1mo")
    interval = request.args.get("interval", "1d")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    tickers = [t for t in tickers if t not in EXCLUDED_TICKERS]

    # Try live data first
    live = _try_yfinance(tickers, period, interval)
    if live:
        return jsonify({"data": live, "source": "live"})

    # Fallback to simulation
    all_sim = _generate_price_history(period, interval)
    result = {t: all_sim[t] for t in tickers if t in all_sim}
    return jsonify({"data": result, "source": "simulated"})


@app.route("/api/quotes")
def get_quotes():
    tickers = request.args.get("tickers", "SPY").split(",")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    tickers = [t for t in tickers if t not in EXCLUDED_TICKERS]

    # Try yfinance
    try:
        import yfinance as yf
        result = {}
        for ticker in tickers:
            t = yf.Ticker(ticker)
            info = t.fast_info
            if hasattr(info, 'last_price') and info.last_price:
                result[ticker] = {
                    "price": round(float(info.last_price), 2),
                    "previousClose": round(float(info.previous_close), 2) if hasattr(info, 'previous_close') else None,
                }
        if result:
            return jsonify({"data": result, "source": "live"})
    except Exception:
        pass

    # Fallback: use latest simulated close
    sim = _generate_price_history("1mo", "1d")
    result = {}
    for ticker in tickers:
        if ticker in sim and sim[ticker]["close"]:
            closes = sim[ticker]["close"]
            result[ticker] = {
                "price": closes[-1],
                "previousClose": closes[-2] if len(closes) > 1 else closes[-1],
            }
    return jsonify({"data": result, "source": "simulated"})


@app.route("/api/macro")
def get_macro():
    # Try to get macro from simulation data
    sim = _generate_price_history("3mo", "1d")
    indicators = {}

    def _trend(ticker, label):
        if ticker in sim:
            closes = sim[ticker]["close"]
            if len(closes) > 21:
                now_p = closes[-1]
                m1 = closes[-min(21, len(closes))]
                m3 = closes[0]
                return {
                    "current": round(now_p, 2),
                    "change_1m": round((now_p - m1) / m1 * 100, 2),
                    "change_3m": round((now_p - m3) / m3 * 100, 2),
                }
        return None

    spy_data = _trend("SPY", "S&P 500")
    if spy_data:
        spy_data["trend"] = "Bullish" if spy_data["change_1m"] > 0 else "Bearish"
        indicators["spy"] = spy_data

    tlt_data = _trend("TLT", "Bonds")
    if tlt_data:
        tlt_data["signal"] = "Rates Falling" if tlt_data["change_1m"] > 0 else "Rates Rising"
        indicators["bonds"] = tlt_data

    gld_data = _trend("GLD", "Gold")
    if gld_data:
        gld_data["demand"] = "Elevated" if gld_data["change_1m"] > 2 else "Normal"
        indicators["gold"] = gld_data

    eem_data = _trend("EEM", "EM")
    if eem_data:
        eem_data["trend"] = "Risk-On" if eem_data["change_1m"] > 0 else "Risk-Off"
        indicators["em"] = eem_data

    uso_data = _trend("USO", "Oil")
    if uso_data:
        indicators["oil"] = uso_data

    # Synthetic VIX from SPY vol
    if "SPY" in sim:
        spy_closes = sim["SPY"]["close"]
        if len(spy_closes) > 20:
            rets = [(spy_closes[i] - spy_closes[i-1]) / spy_closes[i-1] for i in range(max(1, len(spy_closes)-20), len(spy_closes))]
            daily_vol = (sum(r**2 for r in rets) / len(rets)) ** 0.5
            vix_approx = daily_vol * math.sqrt(252) * 100
            indicators["vix"] = {
                "current": round(vix_approx, 1),
                "regime": "Low Vol" if vix_approx < 15 else "Moderate" if vix_approx < 25 else "High Vol",
            }

    # Overall regime
    spy_1m = indicators.get("spy", {}).get("change_1m", 0)
    vix = indicators.get("vix", {}).get("current", 20)
    if spy_1m > 2 and vix < 20:
        regime = "Risk-On"
    elif spy_1m < -2 or vix > 25:
        regime = "Risk-Off"
    else:
        regime = "Neutral"
    indicators["regime"] = regime
    indicators["source"] = "simulated"

    return jsonify(indicators)


@app.route("/api/reassess", methods=["POST"])
def reassess():
    """
    Daily reassessment engine.
    Takes current portfolio + macro, returns rebalance recommendation.
    Implements PM decision framework:
      1. Regime detection
      2. Signal scoring
      3. Allocation adjustment rules
    """
    data = request.get_json() or {}
    current_portfolio = data.get("portfolio", [])
    macro = json.loads(get_macro().get_data(as_text=True))

    regime = macro.get("regime", "Neutral")
    spy = macro.get("spy", {})
    vix = macro.get("vix", {})
    bonds = macro.get("bonds", {})
    gold = macro.get("gold", {})
    em = macro.get("em", {})
    oil = macro.get("oil", {})

    spy_1m = spy.get("change_1m", 0)
    spy_3m = spy.get("change_3m", 0)
    vix_level = vix.get("current", 20)
    tlt_1m = bonds.get("change_1m", 0)
    gld_1m = gold.get("change_1m", 0)
    em_1m = em.get("change_1m", 0)
    oil_1m = oil.get("change_1m", 0)

    # --- Signal scoring ---
    signals = []
    triggers = []

    # 1. Regime shift detection
    if regime == "Risk-Off":
        signals.append({"signal": "REGIME_RISK_OFF", "weight": -3,
                        "reason": f"Market regime shifted to Risk-Off (SPY {spy_1m:+.1f}%, VIX {vix_level:.0f})"})
        triggers.append("regime_shift")
    elif regime == "Risk-On" and vix_level < 15:
        signals.append({"signal": "REGIME_RISK_ON_LOW_VOL", "weight": 2,
                        "reason": f"Strong Risk-On with low volatility (VIX {vix_level:.1f})"})

    # 2. Volatility spike
    if vix_level > 25:
        signals.append({"signal": "VIX_SPIKE", "weight": -2,
                        "reason": f"VIX elevated at {vix_level:.1f} — defensive positioning warranted"})
        triggers.append("vix_spike")
    elif vix_level > 30:
        signals.append({"signal": "VIX_EXTREME", "weight": -4,
                        "reason": f"VIX at {vix_level:.1f} — extreme fear, max defensive"})
        triggers.append("vix_extreme")

    # 3. Rate direction
    if tlt_1m > 3:
        signals.append({"signal": "RATES_FALLING_FAST", "weight": 1,
                        "reason": f"Rates falling sharply (TLT {tlt_1m:+.1f}%) — favour growth + duration"})
    elif tlt_1m < -3:
        signals.append({"signal": "RATES_RISING_FAST", "weight": -1,
                        "reason": f"Rates rising sharply (TLT {tlt_1m:+.1f}%) — reduce duration, favour value"})
        triggers.append("rates_rising")

    # 4. Gold breakout
    if gld_1m > 5:
        signals.append({"signal": "GOLD_BREAKOUT", "weight": 1,
                        "reason": f"Gold surging {gld_1m:+.1f}% — increase safe haven allocation"})
        triggers.append("gold_breakout")
    elif gld_1m < -3:
        signals.append({"signal": "GOLD_WEAKNESS", "weight": -1,
                        "reason": f"Gold weak {gld_1m:+.1f}% — reduce gold allocation"})

    # 5. EM divergence
    if em_1m > 3 and spy_1m < em_1m:
        signals.append({"signal": "EM_OUTPERFORM", "weight": 1,
                        "reason": f"EM outperforming ({em_1m:+.1f}% vs SPY {spy_1m:+.1f}%) — increase EM"})
    elif em_1m < -3:
        signals.append({"signal": "EM_WEAKNESS", "weight": -1,
                        "reason": f"EM under pressure ({em_1m:+.1f}%) — reduce EM exposure"})

    # 6. SPY trend strength
    if spy_1m > 5:
        signals.append({"signal": "SPY_MOMENTUM", "weight": 1,
                        "reason": f"Strong equity momentum (SPY {spy_1m:+.1f}% 1M)"})
    elif spy_1m < -5:
        signals.append({"signal": "SPY_SELLOFF", "weight": -3,
                        "reason": f"Significant equity selloff (SPY {spy_1m:+.1f}% 1M)"})
        triggers.append("equity_selloff")

    # --- Aggregate score ---
    total_score = sum(s["weight"] for s in signals)

    # --- Generate recommended allocation ---
    # Start from base allocation, adjust based on score
    if total_score <= -4:
        # Defensive: heavy bonds + gold, minimal equity
        recommended = {
            "GLD": 20, "TLT": 15, "BND": 15,
            "AAPL": 10, "MSFT": 8, "SPY": 10,
            "NVDA": 7, "AMZN": 5, "INDA": 5, "ICLN": 5,
        }
        stance = "Defensive"
        rationale = "Multiple bearish signals triggered. Rotating to 50% safe haven (gold + bonds), reducing equity beta. Preserving capital is priority."
    elif total_score <= -2:
        # Cautious: increase hedges, trim risk
        recommended = {
            "NVDA": 12, "AAPL": 14, "MSFT": 12, "GLD": 15,
            "AMZN": 8, "SPY": 8, "TLT": 10, "BND": 8,
            "INDA": 7, "ICLN": 6,
        }
        stance = "Cautious"
        rationale = "Bearish signals emerging. Increasing gold to 15% and bonds to 18%. Trimming NVDA from 18% to 12%. Maintaining quality tech names."
    elif total_score >= 3:
        # Aggressive: max equity, trim hedges
        recommended = {
            "NVDA": 22, "AAPL": 14, "MSFT": 13, "AMZN": 12,
            "SPY": 10, "INDA": 10, "ICLN": 8, "GLD": 6,
            "TLT": 3, "BND": 2,
        }
        stance = "Aggressive"
        rationale = "Strong bullish confluence. Increasing NVDA to 22%, adding to AMZN and INDA. Trimming hedges to 11%. Maximum risk-on positioning."
    elif total_score >= 1:
        # Moderately bullish: slight tilt to risk
        recommended = {
            "NVDA": 20, "AAPL": 14, "MSFT": 12, "GLD": 10,
            "AMZN": 11, "SPY": 9, "INDA": 8, "ICLN": 7,
            "TLT": 5, "BND": 4,
        }
        stance = "Moderately Bullish"
        rationale = "Positive signals outweigh risks. Increasing NVDA to 20% and AMZN to 11%. Slight trim to hedges. Maintaining core positioning."
    else:
        # Neutral: hold current base allocation
        recommended = {
            "NVDA": 18, "AAPL": 14, "MSFT": 12, "GLD": 12,
            "AMZN": 10, "SPY": 8, "INDA": 8, "ICLN": 7,
            "TLT": 6, "BND": 5,
        }
        stance = "Hold"
        rationale = "No strong directional signals. Maintaining current allocation. Will reassess tomorrow."

    # Check if rebalance is needed (allocation drift > 3% on any position)
    should_rebalance = len(triggers) > 0
    if not should_rebalance and current_portfolio:
        current_allocs = {p.get("ticker"): p.get("allocation", 0) for p in current_portfolio}
        for ticker, target in recommended.items():
            current = current_allocs.get(ticker, 0)
            if abs(current - target) > 3:
                should_rebalance = True
                triggers.append(f"drift_{ticker}")
                break

    return jsonify({
        "date": datetime.utcnow().isoformat(),
        "regime": regime,
        "stance": stance,
        "score": total_score,
        "signals": signals,
        "triggers": triggers,
        "shouldRebalance": should_rebalance,
        "recommended": recommended,
        "rationale": rationale,
        "macro_snapshot": {
            "spy_1m": spy_1m, "vix": vix_level,
            "tlt_1m": tlt_1m, "gld_1m": gld_1m,
            "em_1m": em_1m, "oil_1m": oil_1m,
        },
    })


@app.route("/api/validate_ticker")
def validate_ticker():
    ticker = request.args.get("ticker", "").strip().upper()
    if ticker in EXCLUDED_TICKERS:
        return jsonify({"valid": False, "reason": "Excluded: defense/weapons sector"})
    if ticker in ASSET_UNIVERSE:
        sim = _generate_price_history("1mo", "1d")
        price = sim[ticker]["close"][-1] if ticker in sim else 0
        return jsonify({"valid": True, "price": round(price, 2)})
    return jsonify({"valid": False, "reason": "Not in universe"})


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Portfolio Trading Simulator")
    print(f"  http://localhost:{port}")
    print(f"  {len(ASSET_UNIVERSE)} assets | {len(EXCLUDED_TICKERS)} excluded (defense)")
    print(f"  Mode: Live (yfinance) with simulation fallback\n")
    app.run(host="0.0.0.0", port=port, debug=False)
