// ============================================================
// Trading Simulator — UI Layer (API-backed)
// ============================================================

(function () {
  'use strict';

  const CHART_COLORS = [
    '#2979ff', '#00c853', '#ff6d00', '#aa00ff',
    '#00bcd4', '#ffab00', '#ff1744', '#69f0ae', '#78909c', '#e040fb'
  ];

  let performanceChart = null;
  let allocationChart = null;
  let currentPeriod = '1m';

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  function fmt$(v) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v);
  }
  function fmtPct(v) {
    const sign = v >= 0 ? '+' : '';
    return sign + v.toFixed(2) + '%';
  }
  function pnlClass(v) { return v >= 0 ? 'pnl-positive' : 'pnl-negative'; }

  function showLoading(el) {
    if (typeof el === 'string') el = $(el);
    if (el) el.style.opacity = '0.5';
  }
  function hideLoading(el) {
    if (typeof el === 'string') el = $(el);
    if (el) el.style.opacity = '1';
  }

  // --- Init ---
  document.addEventListener('DOMContentLoaded', async () => {
    showLoading('#app-loader');
    try {
      await Simulator.init();
      await renderAll();
      // Show data source
      const src = Simulator.getDataSource();
      const badge = $('#data-source-badge');
      if (badge) {
        badge.textContent = src === 'live' ? 'Live Data' : 'Simulated Data';
        badge.className = 'header-badge ' + (src === 'live' ? '' : 'simulated');
      }
    } catch (err) {
      console.error('Init error:', err);
      showError('Failed to initialize. Make sure the server is running (python server.py).');
    }
    hideLoading('#app-loader');
    $('#app-loader').style.display = 'none';
    $('#app-main').style.display = 'grid';
  });

  function showError(msg) {
    const loader = $('#app-loader');
    if (loader) {
      loader.innerHTML = `<div style="color:var(--red);text-align:center;padding:40px;">${msg}</div>`;
    }
  }

  async function renderAll() {
    renderHeader();
    await renderReturnsCards();
    await renderPerformanceChart(currentPeriod);
    renderAllocationChart();
    renderPositionsTable();
    renderMacroView();
    await renderReassessment();
    renderKeyDrivers();
    await renderRiskMetrics();
    setupRebalanceForm();
  }

  // --- Header ---
  function renderHeader() {
    const total = Simulator.getTotalValue();
    const pnl = total - Simulator.INITIAL_CAPITAL;
    const pnlPct = (pnl / Simulator.INITIAL_CAPITAL) * 100;

    $('#total-value').textContent = fmt$(total);
    $('#total-value').className = 'stat-value ' + pnlClass(pnl);
    $('#total-pnl').textContent = `${fmtPct(pnlPct)} (${fmt$(pnl)})`;
    $('#total-pnl').className = 'stat-sub ' + pnlClass(pnl);
    $('#initial-capital').textContent = fmt$(Simulator.INITIAL_CAPITAL);

    const macro = Simulator.getMacroData();
    const regimeBadge = $('#regime-badge');
    const regime = macro.regime || 'Neutral';
    regimeBadge.textContent = regime;
    regimeBadge.className = 'regime-badge ' +
      (regime === 'Risk-On' ? 'risk-on' : regime === 'Risk-Off' ? 'risk-off' : 'neutral');
  }

  // --- Returns Cards ---
  async function renderReturnsCards() {
    const container = $('#returns-grid');
    container.innerHTML = '<div style="color:var(--text-muted);padding:8px;">Loading returns...</div>';

    try {
      const returns = await Simulator.getReturns();
      container.innerHTML = '';

      Object.keys(Simulator.PERIODS).forEach(key => {
        const val = returns[key] || 0;
        const card = document.createElement('div');
        card.className = 'return-card' + (key === currentPeriod ? ' active' : '');
        card.dataset.period = key;
        card.innerHTML = `
          <div class="return-period">${Simulator.PERIODS[key].label}</div>
          <div class="return-value ${pnlClass(val)}">${fmtPct(val)}</div>
        `;
        card.addEventListener('click', async () => {
          currentPeriod = key;
          $$('.return-card').forEach(c => c.classList.remove('active'));
          card.classList.add('active');
          await renderPerformanceChart(key);
        });
        container.appendChild(card);
      });
    } catch (err) {
      container.innerHTML = '<div style="color:var(--red)">Failed to load returns</div>';
    }
  }

  // --- Performance Chart ---
  async function renderPerformanceChart(periodKey) {
    const canvas = $('#performance-canvas');
    showLoading(canvas.parentElement);

    try {
      const series = await Simulator.getPortfolioValueSeries(periodKey);
      const ctx = canvas.getContext('2d');

      if (performanceChart) performanceChart.destroy();

      if (series.values.length === 0) {
        hideLoading(canvas.parentElement);
        return;
      }

      const isPositive = series.values[series.values.length - 1] >= series.values[0];
      const lineColor = isPositive ? '#00c853' : '#ff1744';
      const fillColor = isPositive ? 'rgba(0, 200, 83, 0.08)' : 'rgba(255, 23, 68, 0.08)';

      performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: series.timestamps,
          datasets: [{
            label: 'Portfolio Value',
            data: series.values,
            borderColor: lineColor,
            backgroundColor: fillColor,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHitRadius: 10,
            borderWidth: 2,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { intersect: false, mode: 'index' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#1a1f2b',
              borderColor: '#2a3040',
              borderWidth: 1,
              titleColor: '#8b95a8',
              bodyColor: '#e1e4ea',
              bodyFont: { family: "'SF Mono', monospace" },
              callbacks: {
                title: (items) => {
                  const d = new Date(items[0].label);
                  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                },
                label: (item) => ' ' + fmt$(item.parsed.y),
              }
            }
          },
          scales: {
            x: {
              type: 'time',
              ticks: { color: '#5a6478', maxTicksLimit: 8, font: { size: 11 } },
              grid: { color: 'rgba(30, 37, 51, 0.5)' },
            },
            y: {
              ticks: {
                color: '#5a6478',
                font: { size: 11, family: "'SF Mono', monospace" },
                callback: v => '$' + v.toFixed(0),
              },
              grid: { color: 'rgba(30, 37, 51, 0.5)' },
            }
          }
        }
      });
    } catch (err) {
      console.error('Chart error:', err);
    }

    hideLoading(canvas.parentElement);
  }

  // --- Allocation Chart ---
  function renderAllocationChart() {
    const data = Simulator.getAllocationData();
    const ctx = $('#allocation-canvas').getContext('2d');

    if (allocationChart) allocationChart.destroy();

    allocationChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.map(d => d.ticker),
        datasets: [{
          data: data.map(d => d.allocation),
          backgroundColor: CHART_COLORS.slice(0, data.length),
          borderColor: '#141820',
          borderWidth: 2,
          hoverBorderColor: '#e1e4ea',
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#8b95a8',
              padding: 10,
              font: { size: 11 },
              usePointStyle: true,
              pointStyleWidth: 8,
            }
          },
          tooltip: {
            backgroundColor: '#1a1f2b',
            borderColor: '#2a3040',
            borderWidth: 1,
            bodyColor: '#e1e4ea',
            callbacks: {
              label: (item) => ` ${item.label}: ${item.raw.toFixed(1)}% (${fmt$(data[item.dataIndex].value)})`
            }
          }
        }
      }
    });
  }

  // --- Positions Table ---
  function renderPositionsTable() {
    const positions = Simulator.getPositions();
    const tbody = $('#positions-tbody');
    tbody.innerHTML = '';

    for (const pos of positions) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="name-cell">${pos.name}</td>
        <td class="ticker-cell">${pos.ticker}</td>
        <td class="right">${pos.sector}</td>
        <td class="right">${pos.category}</td>
        <td class="right">${fmt$(pos.currentPrice)}</td>
        <td class="right">${pos.shares.toFixed(4)}</td>
        <td class="right">${fmt$(pos.currentValue)}</td>
        <td class="right ${pnlClass(pos.pnl)}">${fmt$(pos.pnl)}</td>
        <td class="right ${pnlClass(pos.pnlPct)}">${fmtPct(pos.pnlPct)}</td>
        <td class="right">${pos.allocation.toFixed(1)}%</td>
      `;
      tbody.appendChild(tr);
    }

    // Totals row
    const total = Simulator.getTotalValue();
    const totalPnl = total - Simulator.INITIAL_CAPITAL;
    const totalPnlPct = (totalPnl / Simulator.INITIAL_CAPITAL) * 100;
    const tfoot = document.createElement('tr');
    tfoot.style.fontWeight = '700';
    tfoot.style.borderTop = '2px solid var(--border)';
    tfoot.innerHTML = `
      <td class="name-cell">Total</td>
      <td></td><td></td><td></td><td></td><td></td>
      <td class="right">${fmt$(total)}</td>
      <td class="right ${pnlClass(totalPnl)}">${fmt$(totalPnl)}</td>
      <td class="right ${pnlClass(totalPnlPct)}">${fmtPct(totalPnlPct)}</td>
      <td class="right">100.0%</td>
    `;
    tbody.appendChild(tfoot);
  }

  // --- Macro View ---
  function renderMacroView() {
    const macro = Simulator.getMacroData();
    const container = $('#macro-content');

    const items = [];

    if (macro.spy) {
      items.push({ label: 'S&P 500', value: `$${macro.spy.current}`, sub: `${macro.spy.change_1m > 0 ? '+' : ''}${macro.spy.change_1m}% (1M)`, cls: pnlClass(macro.spy.change_1m) });
    }
    if (macro.vix) {
      items.push({ label: 'VIX', value: macro.vix.current.toFixed(1), sub: macro.vix.regime, cls: macro.vix.current > 25 ? 'pnl-negative' : macro.vix.current < 15 ? 'pnl-positive' : '' });
    }
    if (macro.bonds) {
      items.push({ label: 'Rates Signal', value: macro.bonds.signal, sub: `TLT: ${macro.bonds.change_1m > 0 ? '+' : ''}${macro.bonds.change_1m}%`, cls: '' });
    }
    if (macro.gold) {
      items.push({ label: 'Gold', value: `$${macro.gold.current}`, sub: `${macro.gold.change_1m > 0 ? '+' : ''}${macro.gold.change_1m}% | ${macro.gold.demand}`, cls: pnlClass(macro.gold.change_1m) });
    }
    if (macro.em) {
      items.push({ label: 'EM Sentiment', value: macro.em.trend, sub: `EEM: ${macro.em.change_1m > 0 ? '+' : ''}${macro.em.change_1m}%`, cls: pnlClass(macro.em.change_1m) });
    }
    if (macro.oil) {
      items.push({ label: 'Oil (USO)', value: `$${macro.oil.current}`, sub: `${macro.oil.change_1m > 0 ? '+' : ''}${macro.oil.change_1m}% (1M)`, cls: pnlClass(macro.oil.change_1m) });
    }

    items.push({ label: 'Market Regime', value: macro.regime || 'Neutral', cls: macro.regime === 'Risk-On' ? 'pnl-positive' : macro.regime === 'Risk-Off' ? 'pnl-negative' : '' });

    container.innerHTML = items.map(item => `
      <div class="sentiment-card">
        <div class="sentiment-type">${item.label}</div>
        <div class="sentiment-signal ${item.cls || ''}">${item.value}</div>
        ${item.sub ? `<div style="font-size:0.7rem;color:var(--text-muted);margin-top:4px;">${item.sub}</div>` : ''}
      </div>
    `).join('');
  }

  // --- Key Drivers ---
  function renderKeyDrivers() {
    const drivers = Simulator.getKeyDrivers();

    const contribContainer = $('#contributors');
    contribContainer.innerHTML = drivers.contributors.map(d => `
      <div class="driver-item positive">
        <div>
          <span class="driver-name">${d.ticker}</span>
          <span style="color:var(--text-muted);font-size:0.75rem;margin-left:6px;">${d.name}</span>
        </div>
        <span class="driver-value pnl-positive">${fmt$(d.pnl)} (${fmtPct(d.pnlPct)})</span>
      </div>
    `).join('') || '<div style="color:var(--text-muted)">No positive contributors</div>';

    const detractContainer = $('#detractors');
    detractContainer.innerHTML = drivers.detractors.map(d => `
      <div class="driver-item negative">
        <div>
          <span class="driver-name">${d.ticker}</span>
          <span style="color:var(--text-muted);font-size:0.75rem;margin-left:6px;">${d.name}</span>
        </div>
        <span class="driver-value pnl-negative">${fmt$(d.pnl)} (${fmtPct(d.pnlPct)})</span>
      </div>
    `).join('') || '<div style="color:var(--text-muted)">No detractors</div>';
  }

  // --- Risk Metrics ---
  async function renderRiskMetrics() {
    const container = $('#risk-metrics');
    container.innerHTML = '<div style="color:var(--text-muted);padding:8px;">Calculating...</div>';

    try {
      const risk = await Simulator.getRiskMetrics();
      if (!risk.annualizedReturn) {
        container.innerHTML = '<div style="color:var(--text-muted)">Insufficient data for risk metrics</div>';
        return;
      }

      const items = [
        { label: 'Annual Return', value: risk.annualizedReturn + '%', cls: pnlClass(parseFloat(risk.annualizedReturn)) },
        { label: 'Annual Volatility', value: risk.annualizedVol + '%' },
        { label: 'Sharpe Ratio', value: risk.sharpeRatio, cls: parseFloat(risk.sharpeRatio) >= 1 ? 'pnl-positive' : '' },
        { label: 'Max Drawdown', value: '-' + risk.maxDrawdown + '%', cls: 'pnl-negative' },
        { label: 'VaR 95% (Daily)', value: fmt$(risk.var95Dollar) },
        { label: 'Concentration (HHI)', value: risk.concentrationHHI },
      ];

      container.innerHTML = items.map(item => `
        <div class="metric-card">
          <div class="metric-label">${item.label}</div>
          <div class="metric-value ${item.cls || ''}">${item.value}</div>
        </div>
      `).join('');
    } catch (err) {
      container.innerHTML = '<div style="color:var(--red)">Failed to compute risk metrics</div>';
    }
  }

  // --- Daily Reassessment ---
  async function renderReassessment() {
    const container = $('#reassessment-content');
    if (!container) return;

    // Auto-run if needed today
    let result;
    if (Simulator.needsReassessment()) {
      container.innerHTML = '<div style="color:var(--text-muted);padding:8px;">Running daily reassessment...</div>';
      try {
        result = await Simulator.runReassessment();
      } catch (err) {
        container.innerHTML = '<div style="color:var(--red)">Reassessment failed</div>';
        return;
      }
    } else {
      const history = Simulator.getReassessmentHistory();
      result = history[0];
    }

    if (!result) {
      container.innerHTML = '<div style="color:var(--text-muted)">No reassessment data</div>';
      return;
    }

    // Stance badge color
    const stanceColors = {
      'Aggressive': 'pnl-positive',
      'Moderately Bullish': 'pnl-positive',
      'Hold': '',
      'Cautious': 'pnl-negative',
      'Defensive': 'pnl-negative',
    };

    const stanceBg = {
      'Aggressive': 'var(--green-dim)',
      'Moderately Bullish': 'var(--green-dim)',
      'Hold': 'var(--blue-dim)',
      'Cautious': 'var(--amber-dim)',
      'Defensive': 'var(--red-dim)',
    };

    // Group signals by category
    const macroSignals = (result.signals || []).filter(s => s.category !== 'Micro');
    const microSignals = (result.signals || []).filter(s => s.category === 'Micro');

    function renderSignalList(signals) {
      return signals.map(s => {
        const color = s.weight > 0 ? 'var(--green)' : s.weight < 0 ? 'var(--red)' : 'var(--text-muted)';
        const sign = s.weight > 0 ? '+' : '';
        const catColor = s.category === 'Regime' ? 'var(--blue)' : s.category === 'Credit' ? 'var(--amber)' :
          s.category === 'Inflation' ? 'var(--red)' : 'var(--text-muted)';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;margin-bottom:4px;border-radius:4px;background:rgba(255,255,255,0.02);border:1px solid var(--border);">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:0.6rem;text-transform:uppercase;letter-spacing:0.5px;color:${catColor};min-width:65px;">${s.category}</span>
            <span style="font-size:0.8rem;">${s.detail || s.reason || ''}</span>
          </div>
          <span style="font-family:var(--font-mono);font-weight:700;color:${color};min-width:30px;text-align:right;">${sign}${s.weight}</span>
        </div>`;
      }).join('');
    }

    const macroSignalsHtml = renderSignalList(macroSignals);
    const microSignalsHtml = renderSignalList(microSignals);

    // Position scores table
    const posScores = result.positionScores || {};
    const posScoresHtml = Object.entries(posScores).map(([ticker, ps]) => {
      const scoreColor = ps.score > 0 ? 'var(--green)' : ps.score < 0 ? 'var(--red)' : 'var(--text-muted)';
      const rsColor = ps.relative_strength > 0 ? 'var(--green)' : ps.relative_strength < 0 ? 'var(--red)' : 'var(--text-muted)';
      return `<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;margin:2px;border-radius:4px;background:rgba(255,255,255,0.02);border:1px solid var(--border);font-size:0.78rem;">
        <strong>${ticker}</strong>
        <span style="color:${scoreColor};font-family:var(--font-mono);">${ps.score > 0 ? '+' : ''}${ps.score}</span>
        <span style="color:var(--text-muted);font-size:0.68rem;">RS:${ps.relative_strength > 0 ? '+' : ''}${ps.relative_strength}</span>
        <span style="color:var(--text-muted);font-size:0.68rem;">Mom:${ps.momentum > 0 ? '+' : ''}${ps.momentum}</span>
        <span style="color:var(--text-muted);font-size:0.68rem;">Vol:${ps.volatility}%</span>
      </div>`;
    }).join('');

    // Recommended allocation changes
    const currentPositions = Simulator.getPositions();
    const currentAllocs = {};
    for (const p of currentPositions) currentAllocs[p.ticker] = Math.round(p.allocation);

    const changesHtml = Object.entries(result.recommended)
      .map(([ticker, target]) => {
        const current = currentAllocs[ticker] || 0;
        const diff = target - current;
        if (Math.abs(diff) < 1) return '';
        const color = diff > 0 ? 'var(--green)' : 'var(--red)';
        const arrow = diff > 0 ? '&#9650;' : '&#9660;';
        return `<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;margin:2px;border-radius:4px;background:rgba(255,255,255,0.03);border:1px solid var(--border);font-size:0.78rem;">
          <strong>${ticker}</strong>
          <span style="color:var(--text-muted)">${current}%</span>
          <span style="color:${color}">${arrow} ${target}%</span>
        </span>`;
      })
      .filter(Boolean)
      .join('');

    const assessDate = new Date(result.date).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    const macroScoreDisplay = result.macroScore !== undefined ? result.macroScore : '?';
    const microScoreDisplay = result.microScore !== undefined ? result.microScore : '?';

    container.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px;">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <span style="padding:5px 14px;border-radius:4px;font-weight:700;font-size:0.85rem;background:${stanceBg[result.stance] || 'var(--blue-dim)'}" class="${stanceColors[result.stance] || ''}">${result.stance}</span>
          <span style="font-family:var(--font-mono);font-size:0.8rem;color:var(--text-muted);">Total: ${result.score > 0 ? '+' : ''}${result.score}</span>
          <span style="font-family:var(--font-mono);font-size:0.72rem;padding:2px 6px;border-radius:3px;background:var(--blue-dim);color:var(--blue);">Macro ${macroScoreDisplay > 0 ? '+' : ''}${macroScoreDisplay}</span>
          <span style="font-family:var(--font-mono);font-size:0.72rem;padding:2px 6px;border-radius:3px;background:rgba(170,0,255,0.15);color:var(--purple);">Micro ${microScoreDisplay > 0 ? '+' : ''}${microScoreDisplay}</span>
          <span style="font-size:0.75rem;color:var(--text-muted);">${assessDate}</span>
        </div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-secondary" id="reassess-btn" style="font-size:0.75rem;padding:6px 14px;">Re-run Now</button>
          ${result.shouldRebalance ? '<button class="btn btn-primary" id="apply-reassess-btn" style="font-size:0.75rem;padding:6px 14px;">Apply Recommendation</button>' : ''}
        </div>
      </div>

      <div style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:14px;line-height:1.6;padding:10px 14px;background:rgba(255,255,255,0.02);border-radius:6px;border:1px solid var(--border);">${result.rationale}</div>

      ${macroSignals.length ? `<div style="margin-bottom:14px;"><div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:var(--blue);margin-bottom:8px;">Macro Signals (${macroSignals.length})</div>${macroSignalsHtml}</div>` : '<div style="color:var(--text-muted);font-size:0.8rem;margin-bottom:14px;">No macro signals triggered.</div>'}

      ${posScoresHtml ? `<div style="margin-bottom:14px;"><div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:var(--purple);margin-bottom:8px;">Position Micro Scores</div><div style="display:flex;flex-wrap:wrap;">${posScoresHtml}</div></div>` : ''}

      ${microSignals.length ? `<div style="margin-bottom:14px;"><div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:var(--purple);margin-bottom:8px;">Micro Signals (${microSignals.length})</div>${microSignalsHtml}</div>` : ''}

      ${changesHtml ? `<div><div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);margin-bottom:8px;">Recommended Changes</div><div style="display:flex;flex-wrap:wrap;">${changesHtml}</div></div>` : '<div style="color:var(--text-muted);font-size:0.8rem;">No allocation changes recommended.</div>'}

      ${result.adjustments && result.adjustments.length ? `<div style="margin-top:10px;font-size:0.72rem;color:var(--text-muted);">Micro tilts: ${result.adjustments.join(', ')}</div>` : ''}
    `;

    // Buttons
    const reassessBtn = $('#reassess-btn');
    if (reassessBtn) {
      reassessBtn.onclick = async () => {
        reassessBtn.disabled = true;
        reassessBtn.textContent = 'Running...';
        localStorage.removeItem("sim_last_reassessment");
        await renderReassessment();
      };
    }

    const applyBtn = $('#apply-reassess-btn');
    if (applyBtn) {
      applyBtn.onclick = async () => {
        applyBtn.disabled = true;
        applyBtn.textContent = 'Applying...';
        await Simulator.rebalance(result.recommended);
        await Simulator.refreshData();
        await renderAll();
      };
    }

    // Render history
    renderReassessmentHistory();
  }

  function renderReassessmentHistory() {
    const historyContainer = $('#reassessment-history');
    if (!historyContainer) return;

    const history = Simulator.getReassessmentHistory();
    if (history.length <= 1) {
      historyContainer.innerHTML = '<div style="color:var(--text-muted);font-size:0.8rem;">No prior assessments yet.</div>';
      return;
    }

    historyContainer.innerHTML = history.slice(1, 8).map(h => {
      const date = new Date(h.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const stanceColor = h.stance === 'Hold' ? 'var(--blue)' :
        h.stance.includes('Bull') || h.stance === 'Aggressive' ? 'var(--green)' : 'var(--red)';
      return `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(30,37,51,0.5);font-size:0.78rem;">
        <span style="color:var(--text-muted);">${date}</span>
        <span style="color:${stanceColor};font-weight:600;">${h.stance}</span>
        <span style="font-family:var(--font-mono);color:var(--text-muted);">Score: ${h.score > 0 ? '+' : ''}${h.score}</span>
        <span style="color:var(--text-muted);">${h.shouldRebalance ? 'Rebalanced' : 'No change'}</span>
      </div>`;
    }).join('');
  }

  // --- Rebalance Form ---
  function setupRebalanceForm() {
    const universe = Simulator.getUniverse();
    const positions = Simulator.getPositions();
    const container = $('#rebalance-grid');
    container.innerHTML = '';

    // Group universe by category
    const categories = {};
    for (const asset of universe) {
      if (!categories[asset.category]) categories[asset.category] = [];
      categories[asset.category].push(asset);
    }

    // Current allocations
    const currentAllocs = {};
    for (const pos of positions) {
      currentAllocs[pos.ticker] = Math.round(pos.allocation);
    }

    // Build selector for each position slot (max 10)
    const portfolio = Simulator.getPortfolio();
    const maxPositions = 10;

    for (let i = 0; i < maxPositions; i++) {
      const pos = portfolio[i];
      const pct = pos ? (currentAllocs[pos.ticker] || Math.round(pos.allocation)) : 0;
      const selectedTicker = pos ? pos.ticker : '';

      const row = document.createElement('div');
      row.className = 'rebalance-row';
      row.innerHTML = `
        <select class="rebalance-select" data-slot="${i}" style="background:var(--bg-primary);color:var(--text-primary);border:1px solid var(--border);border-radius:4px;padding:4px 8px;font-size:0.8rem;min-width:120px;">
          <option value="">-- Select --</option>
          ${Object.entries(categories).map(([cat, assets]) =>
            `<optgroup label="${cat}">
              ${assets.map(a => `<option value="${a.ticker}" ${a.ticker === selectedTicker ? 'selected' : ''}>${a.ticker} — ${a.name}</option>`).join('')}
            </optgroup>`
          ).join('')}
        </select>
        <input type="range" class="rebalance-slider" min="0" max="100" value="${pct}" data-slot="${i}">
        <div class="rebalance-pct" data-slot-pct="${i}">${pct}%</div>
      `;
      container.appendChild(row);
    }

    // Events
    container.querySelectorAll('.rebalance-slider').forEach(slider => {
      slider.addEventListener('input', () => {
        const slot = slider.dataset.slot;
        container.querySelector(`[data-slot-pct="${slot}"]`).textContent = parseInt(slider.value) + '%';
        updateRebalanceTotal();
      });
    });

    updateRebalanceTotal();

    // Submit
    $('#rebalance-btn').onclick = async () => {
      const allocs = {};
      const slots = container.querySelectorAll('.rebalance-row');
      slots.forEach(row => {
        const select = row.querySelector('.rebalance-select');
        const slider = row.querySelector('.rebalance-slider');
        const ticker = select.value;
        const pct = parseInt(slider.value);
        if (ticker && pct > 0) {
          allocs[ticker] = (allocs[ticker] || 0) + pct;
        }
      });

      const sum = Object.values(allocs).reduce((a, b) => a + b, 0);
      if (sum !== 100) return;

      $('#rebalance-btn').disabled = true;
      $('#rebalance-btn').textContent = 'Rebalancing...';

      try {
        await Simulator.rebalance(allocs);
        await Simulator.refreshData();
        await renderAll();
      } catch (err) {
        console.error('Rebalance error:', err);
      }

      $('#rebalance-btn').textContent = 'Apply Rebalance';
    };

    // Normalize
    $('#normalize-btn').onclick = () => {
      const sliders = container.querySelectorAll('.rebalance-slider');
      let sum = 0;
      sliders.forEach(s => { sum += parseInt(s.value); });
      if (sum === 0) return;
      const factor = 100 / sum;
      let newSum = 0;
      const arr = Array.from(sliders);
      arr.forEach((s, i) => {
        let val = Math.round(parseInt(s.value) * factor);
        if (i === arr.length - 1) val = 100 - newSum;
        s.value = val;
        container.querySelector(`[data-slot-pct="${s.dataset.slot}"]`).textContent = val + '%';
        newSum += val;
      });
      updateRebalanceTotal();
    };

    // Reset
    $('#reset-btn').onclick = async () => {
      if (!confirm('Reset portfolio to default allocation? This will clear your current positions.')) return;
      Simulator.resetPortfolio();
      await Simulator.init();
      await renderAll();
    };
  }

  function updateRebalanceTotal() {
    let sum = 0;
    $$('.rebalance-slider').forEach(s => { sum += parseInt(s.value); });
    const totalEl = $('#rebalance-total');
    totalEl.textContent = `Total: ${sum}%`;
    totalEl.className = 'rebalance-total ' + (sum === 100 ? 'valid' : 'invalid');
    $('#rebalance-btn').disabled = sum !== 100;
  }

})();
