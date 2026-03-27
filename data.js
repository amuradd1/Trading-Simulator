// ============================================================
// Trading Simulator — Data Layer (API-backed, dual mode)
// ============================================================

const Simulator = (() => {
  const INITIAL_CAPITAL = 1000;

  const PERIODS = {
    "24h":  { period: "1d",  interval: "5m",  label: "24H" },
    "48h":  { period: "2d",  interval: "15m", label: "48H" },
    "1w":   { period: "5d",  interval: "1h",  label: "1W" },
    "1m":   { period: "1mo", interval: "1d",  label: "1M" },
    "3m":   { period: "3mo", interval: "1d",  label: "3M" },
    "6m":   { period: "6mo", interval: "1d",  label: "6M" },
    "12m":  { period: "1y",  interval: "1d",  label: "12M" },
    "YTD":  { period: "ytd", interval: "1d",  label: "YTD" },
  };

  // PM Allocation — high-conviction, macro-aligned
  // Thesis: AI capex cycle + rate cuts + gold bid + India EM
  const DEFAULT_PORTFOLIO = [
    { ticker: "NVDA",  allocation: 18 },  // Highest conviction: AI semiconductor demand inflecting
    { ticker: "AAPL",  allocation: 14 },  // Cash flow fortress, services momentum, defensive mega-cap
    { ticker: "MSFT",  allocation: 12 },  // Cloud + Copilot AI enterprise spend, margin expansion
    { ticker: "GLD",   allocation: 12 },  // Safe haven elevated, central bank buying, rates falling
    { ticker: "AMZN",  allocation: 10 },  // AWS reacceleration + retail margin underappreciated
    { ticker: "SPY",   allocation: 8 },   // Core beta, regime is Risk-On low vol
    { ticker: "INDA",  allocation: 8 },   // Best structural EM: domestic demand + mfg shift
    { ticker: "ICLN",  allocation: 7 },   // Policy tailwinds, underowned, mean-reverting
    { ticker: "TLT",   allocation: 6 },   // Duration hedge, rates falling signal
    { ticker: "BND",   allocation: 5 },   // Cash proxy with yield — dry powder for rebalance
  ];

  // State
  let portfolio = [];
  let universe = [];
  let priceCache = {};
  let quoteCache = {};
  let macroData = null;
  let dataSource = "unknown"; // "live" or "simulated"
  let isInitialized = false;

  // --- API helpers ---
  async function apiFetch(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
  }

  async function fetchPrices(tickers, period, interval) {
    const key = `${tickers.join(",")}_${period}_${interval}`;
    if (priceCache[key]) return priceCache[key];
    const resp = await apiFetch(`/api/prices?tickers=${tickers.join(",")}&period=${period}&interval=${interval}`);
    const data = resp.data || resp;
    dataSource = resp.source || "unknown";
    priceCache[key] = data;
    return data;
  }

  async function fetchQuotes(tickers) {
    const needed = tickers.filter(t => !quoteCache[t]);
    if (needed.length > 0) {
      const resp = await apiFetch(`/api/quotes?tickers=${needed.join(",")}`);
      const data = resp.data || resp;
      dataSource = resp.source || dataSource;
      Object.assign(quoteCache, data);
    }
    const result = {};
    for (const t of tickers) result[t] = quoteCache[t];
    return result;
  }

  // --- Init ---
  async function init() {
    universe = await apiFetch("/api/universe");

    const saved = localStorage.getItem("sim_portfolio");
    if (saved) {
      try { portfolio = JSON.parse(saved); } catch { portfolio = []; }
    }

    if (!portfolio.length) {
      await initDefaultPortfolio();
    }

    await refreshData();
    isInitialized = true;
  }

  async function initDefaultPortfolio() {
    const tickers = DEFAULT_PORTFOLIO.map(p => p.ticker);
    const quotes = await fetchQuotes(tickers);

    portfolio = DEFAULT_PORTFOLIO.map(p => {
      const asset = universe.find(a => a.ticker === p.ticker) || {};
      const price = quotes[p.ticker]?.price || 0;
      const investedValue = INITIAL_CAPITAL * (p.allocation / 100);
      const shares = price > 0 ? investedValue / price : 0;
      return {
        ticker: p.ticker,
        name: asset.name || p.ticker,
        sector: asset.sector || "Unknown",
        category: asset.category || "Unknown",
        allocation: p.allocation,
        shares,
        costBasis: price,
        investedValue,
      };
    });

    savePortfolio();
  }

  async function refreshData() {
    const tickers = portfolio.map(p => p.ticker);
    if (tickers.length === 0) return;

    const [quotes, macro] = await Promise.all([
      fetchQuotes(tickers),
      apiFetch("/api/macro"),
    ]);

    quoteCache = { ...quoteCache, ...quotes };
    macroData = macro;
  }

  function savePortfolio() {
    localStorage.setItem("sim_portfolio", JSON.stringify(portfolio));
  }

  // --- Portfolio Data ---
  function getPositions() {
    let totalValue = 0;
    const positions = portfolio.map(pos => {
      const quote = quoteCache[pos.ticker];
      const currentPrice = quote?.price || pos.costBasis;
      const currentValue = pos.shares * currentPrice;
      totalValue += currentValue;
      const pnl = currentValue - pos.investedValue;
      const pnlPct = pos.investedValue > 0 ? (pnl / pos.investedValue) * 100 : 0;
      return { ...pos, currentPrice, currentValue, pnl, pnlPct, allocation: 0 };
    });

    for (const pos of positions) {
      pos.allocation = totalValue > 0 ? (pos.currentValue / totalValue) * 100 : 0;
    }
    return positions;
  }

  function getTotalValue() {
    return getPositions().reduce((s, p) => s + p.currentValue, 0);
  }

  function getAllocationData() {
    return getPositions().map(p => ({
      name: p.name, ticker: p.ticker, allocation: p.allocation, value: p.currentValue,
    }));
  }

  // --- Performance Series ---
  async function getPortfolioValueSeries(periodKey) {
    const config = PERIODS[periodKey];
    if (!config) return { timestamps: [], values: [] };

    const tickers = portfolio.map(p => p.ticker);
    const priceData = await fetchPrices(tickers, config.period, config.interval);

    const refTicker = Object.keys(priceData)[0];
    if (!refTicker) return { timestamps: [], values: [] };

    const timestamps = priceData[refTicker].timestamps.map(t => new Date(t));
    const values = timestamps.map((_, i) => {
      let total = 0;
      for (const pos of portfolio) {
        const data = priceData[pos.ticker];
        if (data && data.close[i] !== undefined) {
          total += pos.shares * data.close[i];
        } else {
          total += pos.shares * pos.costBasis;
        }
      }
      return total;
    });

    return { timestamps, values };
  }

  // --- Returns ---
  async function getReturns() {
    const returns = {};
    const tickers = portfolio.map(p => p.ticker);
    const priceData = await fetchPrices(tickers, "1y", "1d");

    const refTicker = Object.keys(priceData)[0];
    if (!refTicker) return returns;

    const len = priceData[refTicker].close.length;
    const timestamps = priceData[refTicker].timestamps;

    const currentValue = portfolio.reduce((s, pos) => {
      const data = priceData[pos.ticker];
      return s + (data && data.close.length ? pos.shares * data.close[len - 1] : 0);
    }, 0);

    const periodDays = {
      "24h": 1, "48h": 2, "1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252, "YTD": -1,
    };

    for (const [key, days] of Object.entries(periodDays)) {
      let idx;
      if (days === -1) {
        const yr = new Date().getFullYear();
        idx = timestamps.findIndex(t => new Date(t).getFullYear() === yr);
        if (idx === -1) idx = 0;
      } else {
        idx = Math.max(0, len - 1 - days);
      }

      const pastValue = portfolio.reduce((s, pos) => {
        const data = priceData[pos.ticker];
        return s + (data && data.close.length ? pos.shares * data.close[idx] : 0);
      }, 0);

      returns[key] = pastValue > 0 ? ((currentValue - pastValue) / pastValue) * 100 : 0;
    }

    return returns;
  }

  // --- Rebalance ---
  async function rebalance(newAllocations) {
    const totalValue = getTotalValue();
    const tickers = Object.keys(newAllocations).filter(t => newAllocations[t] > 0);
    const quotes = await fetchQuotes(tickers);

    portfolio = tickers.map(ticker => {
      const pct = newAllocations[ticker];
      const asset = universe.find(a => a.ticker === ticker) || {};
      const price = quotes[ticker]?.price || 0;
      const targetValue = totalValue * (pct / 100);
      const shares = price > 0 ? targetValue / price : 0;
      return {
        ticker,
        name: asset.name || ticker,
        sector: asset.sector || "Unknown",
        category: asset.category || "Unknown",
        allocation: pct,
        shares,
        costBasis: price,
        investedValue: targetValue,
      };
    });

    priceCache = {};
    savePortfolio();
  }

  // --- Risk Metrics ---
  async function getRiskMetrics() {
    const tickers = portfolio.map(p => p.ticker);
    const priceData = await fetchPrices(tickers, "1y", "1d");

    const refTicker = Object.keys(priceData)[0];
    if (!refTicker) return {};

    const len = priceData[refTicker].close.length;
    const dailyValues = [];
    for (let i = 0; i < len; i++) {
      let total = 0;
      for (const pos of portfolio) {
        const data = priceData[pos.ticker];
        if (data && data.close[i] !== undefined) total += pos.shares * data.close[i];
      }
      dailyValues.push(total);
    }

    const dailyReturns = [];
    for (let i = 1; i < dailyValues.length; i++) {
      if (dailyValues[i - 1] > 0) {
        dailyReturns.push((dailyValues[i] - dailyValues[i - 1]) / dailyValues[i - 1]);
      }
    }

    if (dailyReturns.length < 2) return {};

    const mean = dailyReturns.reduce((s, r) => s + r, 0) / dailyReturns.length;
    const variance = dailyReturns.reduce((s, r) => s + (r - mean) ** 2, 0) / dailyReturns.length;
    const stdDev = Math.sqrt(variance);
    const annualVol = stdDev * Math.sqrt(252);
    const annualReturn = mean * 252;
    const sharpe = annualVol > 0 ? (annualReturn - 0.045) / annualVol : 0;

    let peak = dailyValues[0], maxDD = 0;
    for (const v of dailyValues) {
      if (v > peak) peak = v;
      const dd = (peak - v) / peak;
      if (dd > maxDD) maxDD = dd;
    }

    const sorted = [...dailyReturns].sort((a, b) => a - b);
    const var95 = sorted[Math.floor(sorted.length * 0.05)] || 0;
    const allocations = getAllocationData();
    const hhi = allocations.reduce((s, a) => s + (a.allocation / 100) ** 2, 0);
    const totalValue = getTotalValue();

    return {
      annualizedReturn: (annualReturn * 100).toFixed(1),
      annualizedVol: (annualVol * 100).toFixed(1),
      sharpeRatio: sharpe.toFixed(2),
      maxDrawdown: (maxDD * 100).toFixed(1),
      maxDrawdownDollar: (maxDD * totalValue).toFixed(2),
      var95Daily: (var95 * 100).toFixed(2),
      var95Dollar: (Math.abs(var95) * totalValue).toFixed(2),
      concentrationHHI: (hhi * 10000).toFixed(0),
    };
  }

  function getMacroData() { return macroData || {}; }
  function getDataSource() { return dataSource; }

  function getKeyDrivers() {
    const positions = getPositions();
    const sorted = [...positions].sort((a, b) => b.pnl - a.pnl);
    return {
      contributors: sorted.filter(p => p.pnl > 0).slice(0, 4),
      detractors: sorted.filter(p => p.pnl < 0).slice(0, 4).reverse(),
    };
  }

  function getUniverse() { return [...universe]; }
  function getPortfolio() { return [...portfolio]; }

  function resetPortfolio() {
    localStorage.removeItem("sim_portfolio");
    portfolio = [];
    priceCache = {};
    quoteCache = {};
  }

  return {
    init, refreshData,
    getPositions, getTotalValue, getAllocationData,
    getPortfolioValueSeries, getReturns,
    rebalance, getRiskMetrics,
    getMacroData, getDataSource, getKeyDrivers,
    getUniverse, getPortfolio, resetPortfolio, fetchQuotes,
    INITIAL_CAPITAL, PERIODS,
  };
})();
