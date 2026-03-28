"""
Portfolio Trading Simulator — Backend Server
Dual mode: Live data via yfinance when available, realistic simulation fallback.
"""

import math
import os
import random
import time
from datetime import datetime, timedelta

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


@app.route("/health")
def healthcheck():
    return jsonify({
        "status": "ok",
        "assets": len(ASSET_UNIVERSE),
    })


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
    Daily reassessment engine — full macro + micro framework.
    Scans: regime, rates, inflation, credit, breadth, USD, commodities,
           geopolitics proxy, plus micro (relative strength, momentum, sector rotation).
    """
    data = request.get_json() or {}
    current_portfolio = data.get("portfolio", [])

    # Fetch all price data we need
    sim_3m = _generate_price_history("3mo", "1d")
    sim_1y = _generate_price_history("1y", "1d")

    def _get(ticker, sim, lookback=21):
        """Get current price and % changes at multiple lookbacks."""
        if ticker not in sim:
            return {"current": 0, "chg_1w": 0, "chg_1m": 0, "chg_3m": 0}
        closes = sim[ticker]["close"]
        n = len(closes)
        now = closes[-1] if n > 0 else 0
        w1 = closes[max(0, n - 5)] if n > 5 else now
        m1 = closes[max(0, n - 21)] if n > 21 else now
        m3 = closes[0]
        return {
            "current": round(now, 2),
            "chg_1w": round((now - w1) / w1 * 100, 2) if w1 else 0,
            "chg_1m": round((now - m1) / m1 * 100, 2) if m1 else 0,
            "chg_3m": round((now - m3) / m3 * 100, 2) if m3 else 0,
        }

    def _relative_strength(ticker, benchmark="SPY"):
        """Relative performance of ticker vs benchmark over 1M."""
        t = _get(ticker, sim_3m)
        b = _get(benchmark, sim_3m)
        return round(t["chg_1m"] - b["chg_1m"], 2)

    def _momentum_score(ticker):
        """Price momentum: weighted avg of 1w, 1m, 3m returns."""
        d = _get(ticker, sim_3m)
        return round(d["chg_1w"] * 0.5 + d["chg_1m"] * 0.3 + d["chg_3m"] * 0.2, 2)

    def _volatility(ticker, lookback=20):
        """Realized daily vol (annualized) from last N closes."""
        if ticker not in sim_3m:
            return 0
        closes = sim_3m[ticker]["close"]
        n = len(closes)
        if n < lookback + 1:
            return 0
        rets = [(closes[i] - closes[i-1]) / closes[i-1]
                for i in range(max(1, n - lookback), n) if closes[i-1] > 0]
        if not rets:
            return 0
        variance = sum(r**2 for r in rets) / len(rets)
        return round(math.sqrt(variance) * math.sqrt(252) * 100, 1)

    # ================================================================
    # MACRO SCAN
    # ================================================================
    macro_signals = []

    # 1. Equity market regime (SPY)
    spy = _get("SPY", sim_3m)
    spy_vol = _volatility("SPY")
    vix_approx = spy_vol  # our VIX proxy

    if spy["chg_1m"] > 5 and vix_approx < 15:
        macro_signals.append({"category": "Regime", "signal": "STRONG_RISK_ON", "weight": 3,
                              "detail": f"SPY +{spy['chg_1m']:.1f}% 1M with VIX at {vix_approx:.0f} — strong bullish regime"})
    elif spy["chg_1m"] > 2 and vix_approx < 20:
        macro_signals.append({"category": "Regime", "signal": "RISK_ON", "weight": 2,
                              "detail": f"SPY +{spy['chg_1m']:.1f}% 1M, VIX {vix_approx:.0f} — constructive"})
    elif spy["chg_1m"] < -5 or vix_approx > 30:
        macro_signals.append({"category": "Regime", "signal": "RISK_OFF_SEVERE", "weight": -4,
                              "detail": f"SPY {spy['chg_1m']:+.1f}% 1M, VIX {vix_approx:.0f} — severe risk-off"})
    elif spy["chg_1m"] < -2 or vix_approx > 25:
        macro_signals.append({"category": "Regime", "signal": "RISK_OFF", "weight": -2,
                              "detail": f"SPY {spy['chg_1m']:+.1f}% 1M, VIX {vix_approx:.0f} — risk-off"})

    # 2. Interest rates / yield curve (TLT = long duration, BND = broad)
    tlt = _get("TLT", sim_3m)
    bnd = _get("BND", sim_3m)
    # TLT vs BND spread = yield curve proxy (TLT rising faster = curve flattening/inversion)
    curve_signal = tlt["chg_1m"] - bnd["chg_1m"]

    if tlt["chg_1m"] > 4:
        macro_signals.append({"category": "Rates", "signal": "RATES_PLUNGING", "weight": 2,
                              "detail": f"TLT +{tlt['chg_1m']:.1f}% — rates falling sharply, favours growth + duration"})
    elif tlt["chg_1m"] > 2:
        macro_signals.append({"category": "Rates", "signal": "RATES_FALLING", "weight": 1,
                              "detail": f"TLT +{tlt['chg_1m']:.1f}% — rates declining, supportive for equities"})
    elif tlt["chg_1m"] < -4:
        macro_signals.append({"category": "Rates", "signal": "RATES_SPIKING", "weight": -3,
                              "detail": f"TLT {tlt['chg_1m']:+.1f}% — rates spiking, headwind for growth/duration"})
    elif tlt["chg_1m"] < -2:
        macro_signals.append({"category": "Rates", "signal": "RATES_RISING", "weight": -1,
                              "detail": f"TLT {tlt['chg_1m']:+.1f}% — rates rising, watch duration exposure"})

    if abs(curve_signal) > 3:
        direction = "flattening" if curve_signal > 0 else "steepening"
        macro_signals.append({"category": "Yield Curve", "signal": f"CURVE_{direction.upper()}", "weight": -1 if curve_signal > 3 else 1,
                              "detail": f"Yield curve {direction} (TLT-BND spread {curve_signal:+.1f}pp)"})

    # 3. Inflation proxy (commodities basket: GLD + SLV + USO + DBA)
    gld = _get("GLD", sim_3m)
    slv = _get("SLV", sim_3m)
    uso = _get("USO", sim_3m)
    dba = _get("DBA", sim_3m)
    commodity_avg_1m = (gld["chg_1m"] + slv["chg_1m"] + uso["chg_1m"] + dba["chg_1m"]) / 4

    if commodity_avg_1m > 5:
        macro_signals.append({"category": "Inflation", "signal": "INFLATION_SURGE", "weight": -2,
                              "detail": f"Commodity basket +{commodity_avg_1m:.1f}% 1M — inflation pressures building, headwind for bonds + growth"})
    elif commodity_avg_1m > 2:
        macro_signals.append({"category": "Inflation", "signal": "INFLATION_RISING", "weight": -1,
                              "detail": f"Commodities firming +{commodity_avg_1m:.1f}% 1M — mild inflation signal"})
    elif commodity_avg_1m < -3:
        macro_signals.append({"category": "Inflation", "signal": "DEFLATION_RISK", "weight": 1,
                              "detail": f"Commodities falling {commodity_avg_1m:+.1f}% 1M — disinflationary, supports rate cuts"})

    # 4. Credit stress (HYG vs BND spread = credit risk appetite)
    hyg = _get("HYG", sim_3m)
    credit_spread = hyg["chg_1m"] - bnd["chg_1m"]

    if credit_spread < -3:
        macro_signals.append({"category": "Credit", "signal": "CREDIT_STRESS", "weight": -2,
                              "detail": f"HY underperforming IG by {credit_spread:+.1f}pp — credit stress widening"})
    elif credit_spread > 2:
        macro_signals.append({"category": "Credit", "signal": "CREDIT_HEALTHY", "weight": 1,
                              "detail": f"HY outperforming IG by +{credit_spread:.1f}pp — healthy risk appetite"})

    # 5. USD strength proxy (EM underperformance = strong USD)
    eem = _get("EEM", sim_3m)
    efa = _get("EFA", sim_3m)
    usd_proxy = -(eem["chg_1m"] + efa["chg_1m"]) / 2  # inverse: weak intl = strong USD

    if usd_proxy > 3:
        macro_signals.append({"category": "USD", "signal": "USD_STRONG", "weight": -1,
                              "detail": f"USD strengthening (intl avg {-usd_proxy:+.1f}%) — headwind for EM + commodities"})
    elif usd_proxy < -3:
        macro_signals.append({"category": "USD", "signal": "USD_WEAK", "weight": 1,
                              "detail": f"USD weakening (intl avg +{-usd_proxy:.1f}%) — tailwind for EM + commodities"})

    # 6. Safe haven demand (GLD relative to SPY)
    safe_haven_spread = gld["chg_1m"] - spy["chg_1m"]
    if safe_haven_spread > 5:
        macro_signals.append({"category": "Safe Haven", "signal": "FLIGHT_TO_SAFETY", "weight": -2,
                              "detail": f"Gold outperforming SPY by +{safe_haven_spread:.1f}pp — flight to safety underway"})
    elif safe_haven_spread > 3:
        macro_signals.append({"category": "Safe Haven", "signal": "SAFE_HAVEN_BID", "weight": -1,
                              "detail": f"Gold bid relative to equities (+{safe_haven_spread:.1f}pp) — caution warranted"})

    # 7. Market breadth proxy (IWM vs SPY = small cap participation)
    iwm = _get("IWM", sim_3m)
    breadth_spread = iwm["chg_1m"] - spy["chg_1m"]

    if breadth_spread > 3:
        macro_signals.append({"category": "Breadth", "signal": "BROAD_PARTICIPATION", "weight": 1,
                              "detail": f"Small caps outperforming large (+{breadth_spread:.1f}pp) — healthy breadth"})
    elif breadth_spread < -3:
        macro_signals.append({"category": "Breadth", "signal": "NARROW_LEADERSHIP", "weight": -1,
                              "detail": f"Small caps lagging ({breadth_spread:+.1f}pp) — narrow leadership, fragile rally"})

    # 8. Geopolitical stress proxy (Gold + Oil up together while equities flat/down)
    if gld["chg_1m"] > 2 and uso["chg_1m"] > 2 and spy["chg_1m"] < 1:
        macro_signals.append({"category": "Geopolitical", "signal": "GEO_RISK_ELEVATED", "weight": -1,
                              "detail": f"Gold +{gld['chg_1m']:.1f}% and Oil +{uso['chg_1m']:.1f}% while SPY flat — geopolitical risk priced in"})

    # 9. Sector rotation (QQQ vs SPY = growth vs value)
    qqq = _get("QQQ", sim_3m)
    growth_vs_value = qqq["chg_1m"] - spy["chg_1m"]

    if growth_vs_value > 3:
        macro_signals.append({"category": "Rotation", "signal": "GROWTH_LEADING", "weight": 1,
                              "detail": f"Growth outperforming value by +{growth_vs_value:.1f}pp — risk appetite for tech"})
    elif growth_vs_value < -3:
        macro_signals.append({"category": "Rotation", "signal": "VALUE_ROTATION", "weight": -1,
                              "detail": f"Value outperforming growth by +{-growth_vs_value:.1f}pp — rotation away from tech"})

    # ================================================================
    # MICRO SCAN (for each held position)
    # ================================================================
    micro_signals = []
    position_scores = {}

    held_tickers = [p.get("ticker") for p in current_portfolio if p.get("ticker")]
    if not held_tickers:
        held_tickers = ["NVDA", "AAPL", "MSFT", "GLD", "AMZN", "SPY", "INDA", "ICLN", "TLT", "BND"]

    for ticker in held_tickers:
        if ticker not in ASSET_UNIVERSE:
            continue
        asset = ASSET_UNIVERSE[ticker]
        d = _get(ticker, sim_3m)
        rs = _relative_strength(ticker)
        mom = _momentum_score(ticker)
        vol = _volatility(ticker)

        score = 0
        reasons = []

        # Relative strength
        if rs > 3:
            score += 2
            reasons.append(f"RS +{rs:.1f}pp vs SPY")
        elif rs > 1:
            score += 1
            reasons.append(f"RS +{rs:.1f}pp vs SPY")
        elif rs < -3:
            score -= 2
            reasons.append(f"RS {rs:+.1f}pp vs SPY")
        elif rs < -1:
            score -= 1
            reasons.append(f"RS {rs:+.1f}pp vs SPY")

        # Momentum
        if mom > 3:
            score += 1
            reasons.append(f"Strong momentum ({mom:+.1f})")
        elif mom < -3:
            score -= 1
            reasons.append(f"Weak momentum ({mom:+.1f})")

        # Volatility vs sector norm
        expected_vol = asset.get("annualVol", 0.25) * 100
        vol_ratio = vol / expected_vol if expected_vol > 0 else 1
        if vol_ratio > 1.5:
            score -= 1
            reasons.append(f"Vol elevated ({vol:.0f}% vs {expected_vol:.0f}% norm)")

        # Trend: 1w vs 1m alignment
        if d["chg_1w"] > 0 and d["chg_1m"] > 0:
            score += 1
            reasons.append("Trend aligned (both positive)")
        elif d["chg_1w"] < 0 and d["chg_1m"] < 0:
            score -= 1
            reasons.append("Trend aligned (both negative)")
        elif d["chg_1w"] > 1 and d["chg_1m"] < -1:
            reasons.append("Reversal signal (1W up, 1M down)")

        position_scores[ticker] = {
            "score": score,
            "reasons": reasons,
            "relative_strength": rs,
            "momentum": mom,
            "volatility": vol,
            "chg_1w": d["chg_1w"],
            "chg_1m": d["chg_1m"],
        }

        # Surface strong micro signals
        if score >= 3:
            micro_signals.append({"category": "Micro", "signal": f"{ticker}_STRONG",
                                  "weight": 1, "detail": f"{ticker}: strong micro ({', '.join(reasons[:2])})"})
        elif score <= -3:
            micro_signals.append({"category": "Micro", "signal": f"{ticker}_WEAK",
                                  "weight": -1, "detail": f"{ticker}: weak micro ({', '.join(reasons[:2])})"})

    # ================================================================
    # AGGREGATE SCORING
    # ================================================================
    all_signals = macro_signals + micro_signals
    macro_score = sum(s["weight"] for s in macro_signals)
    micro_score = sum(s["weight"] for s in micro_signals)
    total_score = macro_score + micro_score

    # ================================================================
    # ALLOCATION DECISION
    # ================================================================
    # Base allocation, then adjust positions based on micro scores
    if total_score <= -5:
        base = {"GLD": 22, "TLT": 16, "BND": 14, "AAPL": 10, "MSFT": 8, "SPY": 10,
                "NVDA": 6, "AMZN": 5, "INDA": 4, "ICLN": 5}
        stance = "Defensive"
        rationale = f"Severe bearish confluence ({len([s for s in all_signals if s['weight'] < 0])} negative signals). Rotating to 52% safe haven. Cutting NVDA to 6%. Capital preservation mode."
    elif total_score <= -2:
        base = {"NVDA": 12, "AAPL": 13, "MSFT": 12, "GLD": 16, "AMZN": 8, "SPY": 8,
                "TLT": 11, "BND": 8, "INDA": 6, "ICLN": 6}
        stance = "Cautious"
        rationale = f"Bearish signals outweigh bullish (macro {macro_score:+d}, micro {micro_score:+d}). Increasing hedges to 35%. Trimming high-beta. Maintaining quality."
    elif total_score >= 5:
        base = {"NVDA": 23, "AAPL": 14, "MSFT": 13, "AMZN": 13, "SPY": 10, "INDA": 10,
                "ICLN": 8, "GLD": 5, "TLT": 2, "BND": 2}
        stance = "Aggressive"
        rationale = f"Strong bullish confluence (macro {macro_score:+d}, micro {micro_score:+d}). Max equity at 91%. NVDA 23% as top conviction. Minimal hedges."
    elif total_score >= 2:
        base = {"NVDA": 20, "AAPL": 14, "MSFT": 12, "AMZN": 11, "SPY": 9, "GLD": 9,
                "INDA": 9, "ICLN": 7, "TLT": 5, "BND": 4}
        stance = "Moderately Bullish"
        rationale = f"Positive tilt (macro {macro_score:+d}, micro {micro_score:+d}). Adding to risk. NVDA 20%, trimming hedges to 18%."
    else:
        base = {"NVDA": 18, "AAPL": 14, "MSFT": 12, "GLD": 12, "AMZN": 10, "SPY": 8,
                "INDA": 8, "ICLN": 7, "TLT": 6, "BND": 5}
        stance = "Hold"
        rationale = f"Mixed signals (macro {macro_score:+d}, micro {micro_score:+d}). No strong conviction to change. Maintaining balanced positioning."

    # Apply micro tilts: adjust +/-2% per position based on micro score
    recommended = dict(base)
    adjustments = []
    for ticker, ps in position_scores.items():
        if ticker in recommended:
            if ps["score"] >= 2 and recommended[ticker] < 25:
                adj = min(2, 25 - recommended[ticker])
                recommended[ticker] += adj
                adjustments.append(f"{ticker} +{adj}% (strong micro)")
            elif ps["score"] <= -2 and recommended[ticker] > 2:
                adj = min(2, recommended[ticker] - 2)
                recommended[ticker] -= adj
                adjustments.append(f"{ticker} -{adj}% (weak micro)")

    # Normalize to 100%
    total_alloc = sum(recommended.values())
    if total_alloc != 100:
        diff = 100 - total_alloc
        # Adjust the largest position
        largest = max(recommended, key=recommended.get)
        recommended[largest] += diff

    # Determine triggers
    triggers = []
    if total_score <= -5:
        triggers.append("severe_bearish")
    elif total_score <= -2:
        triggers.append("bearish_tilt")
    elif total_score >= 5:
        triggers.append("strong_bullish")

    # Drift detection
    should_rebalance = len(triggers) > 0
    if not should_rebalance and current_portfolio:
        current_allocs = {p.get("ticker"): p.get("allocation", 0) for p in current_portfolio}
        for ticker, target in recommended.items():
            current = current_allocs.get(ticker, 0)
            if abs(current - target) > 3:
                should_rebalance = True
                triggers.append(f"drift_{ticker}")
                break

    # Build macro environment summary
    regime = "Risk-Off" if total_score <= -3 else "Risk-On" if total_score >= 2 else "Neutral"

    return jsonify({
        "date": datetime.utcnow().isoformat(),
        "regime": regime,
        "stance": stance,
        "score": total_score,
        "macroScore": macro_score,
        "microScore": micro_score,
        "signals": all_signals,
        "triggers": triggers,
        "shouldRebalance": should_rebalance,
        "recommended": recommended,
        "rationale": rationale,
        "adjustments": adjustments,
        "positionScores": position_scores,
        "macro_snapshot": {
            "spy": spy, "vix": round(vix_approx, 1),
            "tlt": tlt, "gld": gld, "eem": eem, "uso": uso,
            "qqq": qqq, "iwm": iwm, "hyg": hyg, "bnd": bnd,
            "commodity_basket_1m": round(commodity_avg_1m, 1),
            "credit_spread": round(credit_spread, 1),
            "usd_proxy": round(usd_proxy, 1),
            "breadth_spread": round(breadth_spread, 1),
            "growth_vs_value": round(growth_vs_value, 1),
            "safe_haven_spread": round(safe_haven_spread, 1),
        },
        "scanCategories": [
            "Regime", "Rates", "Yield Curve", "Inflation", "Credit",
            "USD", "Safe Haven", "Breadth", "Geopolitical", "Rotation", "Micro"
        ],
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
