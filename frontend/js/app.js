// frontend/js/app.js — Slice 4: 6 tab + WebSocket + cache/jobs UI
// region 0: state + utilities
// region 1: tab switching + localStorage
// region 2: WebSocket
// region 3: tab-dashboard
// region 4: tab-alerts
// region 5: tab-settings (cache / etf / index / stock)
// region 6: tab-settings (jobs + cron drawer)
// region 7: tab-stocks
// region 8: boot

// ===== region 0: state + utilities =====================================
const $ = (id) => document.getElementById(id);
const charts = {};
const _state = {
  activeTab: 'dashboard',
  currentDays: 30,
  currentAgg: 'day',
  _taskState: 'idle',  // idle | running | failed | done
  editingJobId: null,
  currentStock: null,
};

function fmtNum(v, d) {
  if (v == null || v === undefined) return '-';
  return Number(v).toFixed(d ?? 2);
}
function changeClass(c) {
  if (c > 0) return 'up';
  if (c < 0) return 'down';
  return 'flat';
}
function fmtPct(v) {
  if (v == null) return '-';
  return (v > 0 ? '+' : '') + fmtNum(v, 2) + '%';
}
function fmtVol(v) {
  if (!v) return '-';
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万';
  return v.toLocaleString();
}
function fmtShares(v) {
  if (!v) return '-';
  return (v / 1e8).toFixed(2);
}
function sparkOption(values, color) {
  return {
    backgroundColor: 'transparent',
    grid: { top: 2, right: 2, bottom: 2, left: 2 },
    xAxis: { type: 'category', show: false, data: values.map((_, i) => i) },
    yAxis: { type: 'value', show: false, scale: true },
    tooltip: { show: false },
    series: [{
      type: 'line', data: values, smooth: true, symbol: 'none',
      lineStyle: { color, width: 1.5 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{ offset: 0, color: color + '40' }, { offset: 1, color: color + '00' }] } },
    }],
  };
}
async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// ===== region 1: tab switching + localStorage ==========================
const TAB_TITLES = {
  dashboard: '仪表盘',
  alerts: '告警中心',
  thermometer: '温度计',
  settings: '数据管理',
  decision: '决策建议',
  stocks: '自选股',
};
function switchTab(tab) {
  _state.activeTab = tab;
  document.querySelectorAll('.tab').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelector(`.nav-item[data-tab="${tab}"]`)?.classList.add('active');
  $(`tab-${tab}`)?.classList.remove('hidden');
  $('topbar-title').textContent = TAB_TITLES[tab] || tab;
  localStorage.setItem('activeTab', tab);
  // period/agg rows only on dashboard
  $('topbar-period').style.display = (tab === 'dashboard') ? 'flex' : 'none';
  $('topbar-agg').style.display = (tab === 'dashboard') ? 'flex' : 'none';
  // Lazy load tab data
  if (tab === 'dashboard') loadDashboard();
  else if (tab === 'alerts') loadAlerts();
  else if (tab === 'settings') {
    const sub = localStorage.getItem('settingsSubtab') || 'settings-cache';
    switchSubtab(sub);
  } else if (tab === 'stocks') loadStocks();
}

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => switchTab(el.dataset.tab));
});

function switchSubtab(sub) {
  document.querySelectorAll('.subtab').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.subpanel').forEach(el => el.classList.remove('active'));
  document.querySelector(`.subtab[data-subtab="${sub}"]`)?.classList.add('active');
  $(sub)?.classList.add('active');
  localStorage.setItem('settingsSubtab', sub);
  if (sub === 'settings-cache') renderCacheStatus();
  else if (sub === 'settings-etf') { renderETFList(); }
  else if (sub === 'settings-index') { renderIndexList(); }
  else if (sub === 'settings-stock') { renderStockList(); }
  else if (sub === 'settings-jobs') { renderJobList(); }
}
document.querySelectorAll('.subtab').forEach(el => {
  el.addEventListener('click', () => switchSubtab(el.dataset.subtab));
});

// ── topbar period / agg buttons ──
document.querySelectorAll('.period-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const v = btn.dataset.days;
    if (v === 'custom') openCustomRange();
    else setDays(parseInt(v, 10), btn);
  });
});
document.querySelectorAll('.agg-btn').forEach(btn => {
  btn.addEventListener('click', () => setAgg(btn.dataset.agg, btn));
});
function setDays(n, btn) {
  _state.currentDays = n;
  localStorage.setItem('currentDays', n);
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  (btn || document.querySelector(`.period-btn[data-days="${n}"]`))?.classList.add('active');
  if (_state.activeTab === 'dashboard') loadDashboard();
}
function setAgg(a, btn) {
  _state.currentAgg = a;
  localStorage.setItem('currentAgg', a);
  document.querySelectorAll('.agg-btn').forEach(b => b.classList.remove('active'));
  (btn || document.querySelector(`.agg-btn[data-agg="${a}"]`))?.classList.add('active');
  if (_state.activeTab === 'dashboard') loadDashboard();
}
function openCustomRange() {
  $('custom-range-modal').classList.add('open');
  // default: currentDays back to today
  const today = new Date().toISOString().slice(0, 10);
  const from = new Date(Date.now() - _state.currentDays * 86400000).toISOString().slice(0, 10);
  $('cr-from').value = from;
  $('cr-to').value = today;
}
function closeCustomRange() { $('custom-range-modal').classList.remove('open'); }
function applyCustomRange() {
  const from = $('cr-from').value, to = $('cr-to').value;
  if (!from || !to) { alert('请选择起止日期'); return; }
  const days = Math.ceil((new Date(to) - new Date(from)) / 86400000) + 1;
  _state.currentDays = days;
  localStorage.setItem('currentDays', days);
  document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.period-btn[data-days="custom"]').classList.add('active');
  closeCustomRange();
  loadDashboard();
}

// ===== region 2: WebSocket =============================================
let _ws = null;
function _initWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${proto}://${location.host}/ws/progress`;
  _ws = new WebSocket(url);
  _ws.onmessage = (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'heartbeat') return;
    // 新格式
    if (m.type === 'job_start') {
      _state._taskState = 'running';
      _updateTaskChip(`运行中: ${m.job_id}`);
      _appendLog(`▶ ${m.job_id} started`);
    } else if (m.type === 'job_done') {
      _state._taskState = 'done';
      _updateTaskChip(`✓ ${m.job_id} 完成`);
      _appendLog(`✓ ${m.job_id} done (${m.duration_ms}ms): ${m.detail || ''}`, 'ok');
      setTimeout(() => { _state._taskState = 'idle'; _updateTaskChip(''); }, 3000);
    } else if (m.type === 'job_error') {
      _state._taskState = 'failed';
      _updateTaskChip(`✗ ${m.job_id} 失败`);
      _appendLog(`✗ ${m.job_id} error: ${m.detail || ''}`, 'err');
    } else if (m.type === 'job_progress') {
      _appendLog(`… ${m.detail || ''}`);
    }
    // 旧格式兼容 (action= refresh/backfill 等)
    else if (m.action === 'refresh' || m.action === 'backfill' || m.action === 'macro_refresh') {
      _state._taskState = 'running';
      _updateTaskChip(`运行中: ${m.action}`);
      _appendLog(`▶ ${m.action}`);
    } else if (m.action === 'done') {
      _state._taskState = 'done';
      _updateTaskChip(`✓ ${m.action} 完成`);
      _appendLog(`✓ done: ${m.detail || ''}`, 'ok');
      setTimeout(() => { _state._taskState = 'idle'; _updateTaskChip(''); }, 3000);
    } else if (m.action === 'error') {
      _state._taskState = 'failed';
      _updateTaskChip(`✗ 失败`);
      _appendLog(`✗ ${m.detail || m.error || 'unknown error'}`, 'err');
    }
  };
  _ws.onclose = () => { setTimeout(_initWS, 3000); };  // 自动重连
}
function _updateTaskChip(text) {
  const chip = $('task-chip');
  if (!text || _state._taskState === 'idle') {
    chip.className = 'task-chip idle';
    chip.textContent = '空闲';
  } else {
    chip.className = 'task-chip ' + _state._taskState;
    chip.textContent = text;
  }
}
function _appendLog(text, cls) {
  const log = $('progress-log');
  if (!log) return;
  const div = document.createElement('div');
  div.className = 'line ' + (cls || '');
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}
function openProgressModal(title) {
  $('progress-title').textContent = title || '运行中...';
  $('progress-log').innerHTML = '';
  $('progress-modal').classList.add('open');
}
function closeProgressModal() {
  $('progress-modal').classList.remove('open');
}
async function refreshAll() {
  openProgressModal('全量刷新 (l0/l1/l3)');
  try {
    const data = await fetchJSON('/api/cache/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    _appendLog(`✓ 全跑: ${data.result}`, 'ok');
  } catch (e) {
    _appendLog(`✗ ${e.message}`, 'err');
  }
}

// ===== region 3: tab-dashboard =========================================
const KL_OPT = {
  backgroundColor: 'transparent',
  grid: { top: 30, right: 20, bottom: 40, left: 65 },
  tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155',
    textStyle: { color: '#e2e8f0', fontSize: 12 }, axisPointer: { type: 'cross', lineStyle: { color: '#475569' } } },
  xAxis: { type: 'category', data: [], axisLine: { lineStyle: { color: '#475569' } }, axisLabel: { color: '#94a3b8', fontSize: 11 } },
  yAxis: { scale: true, axisLine: { lineStyle: { color: '#475569' } }, axisLabel: { color: '#94a3b8', fontSize: 11 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
  dataZoom: [
    { type: 'inside', start: 70, end: 100 },
    { type: 'slider', start: 70, end: 100, height: 18, bottom: 8, borderColor: '#334155',
      fillerColor: 'rgba(59,130,246,0.2)', handleStyle: { color: '#3b82f6' }, textStyle: { color: '#94a3b8' } },
  ],
  series: [{ type: 'candlestick', data: [],
    itemStyle: { color: '#22c55e', color0: '#ef4444', borderColor: '#22c55e', borderColor0: '#ef4444' } }],
};

async function loadDashboard() {
  await loadAlertPanel();
  await Promise.all([loadMacro(), loadKline(), loadETF()]);
  $('dash-status').textContent = `就绪 · ${new Date().toLocaleTimeString()} · ${_state.currentDays}天/${_state.currentAgg}`;
  $('dash-status').classList.remove('err');
}

async function loadAlertPanel() {
  const host = $('dash-alert-panel');
  try {
    const { red, yellow, top } = await fetchJSON('/api/alerts/summary?limit=3');
    host.style.display = 'block';
    // 4 states: success (none), info (only yellow = warning), err (any red)
    let bannerCls = 'status-banner';
    let label = '✓ 无告警';
    if (red > 0) { bannerCls += ' err'; label = '🔴'; }
    else if (yellow > 0) { bannerCls += ' warn'; label = '🟡'; }
    else { bannerCls += ' ok'; label = '🟢'; }
    host.className = bannerCls;
    host.innerHTML = `<b>${label} 告警</b>: <span class="change ${red>0?'down':'flat'}">${red} 红</span> · <span class="change ${yellow>0?'flat':'flat'}">${yellow} 黄</span>` +
      (top.length ? ` — 最近: ${top.map(a => `<span style="color:#cbd5e1;margin-left:8px;">[${a.severity === 'red' ? '严重' : '警告'}] ${a.message}</span>`).join('')}` : '') +
      ` <a href="#" onclick="switchTab('alerts'); return false;" style="float:right;color:#3b82f6;">查看 →</a>`;
  } catch (e) {
    host.style.display = 'none';
  }
}

async function loadMacro() {
  try {
    const { cards } = await fetchJSON('/api/macro/cards');
    const grid = $('macro-grid');
    grid.innerHTML = '';
    for (const c of cards) {
      const div = document.createElement('div');
      div.className = 'macro-card';
      const sparkData = (c.sparkline || []).slice(-30);
      const range = sparkData.length ? `${sparkData[0].date} → ${sparkData[sparkData.length-1].date}` : c.date || '';
      const minV = sparkData.length ? Math.min(...sparkData.map(p => p.value)).toFixed(c.decimals ?? 2) : '-';
      const maxV = sparkData.length ? Math.max(...sparkData.map(p => p.value)).toFixed(c.decimals ?? 2) : '-';
      const tip = `${c.name}\n最近 ${sparkData.length} 期: 最低 ${minV} · 最高 ${maxV}\n范围: ${range}\n数据源: ${c.source || 'akshare'}`;
      div.title = tip;
      div.innerHTML = `
        <div class="name">${c.name}</div>
        <div class="value-row"><span class="value">${fmtNum(c.value, c.decimals)}</span><span class="unit">${c.unit || ''}</span></div>
        <div><span class="change ${changeClass(c.change)}">${c.change > 0 ? '+' : ''}${fmtNum(c.change, c.decimals)}</span>
          <span style="color:#64748b;font-size:10px;margin-left:6px;">${c.date || ''}</span></div>
        <div class="spark"></div>
      `;
      grid.appendChild(div);
      const sparkEl = div.querySelector('.spark');
      const vals = sparkData.map(p => p.value);
      const color = (c.change || 0) >= 0 ? '#ef4444' : '#22c55e';
      const inst = echarts.init(sparkEl, null, { renderer: 'canvas' });
      inst.setOption(sparkOption(vals, color));
    }
  } catch (e) {
    $('macro-grid').innerHTML = `<div style="color:#ef4444;">❌ ${e.message}</div>`;
  }
}

async function loadKline() {
  const symbol = $('symbol').value.trim();
  const freq = $('freq').value;
  $('status').textContent = `加载中: ${symbol} (${freq}) ${_state.currentDays}天/${_state.currentAgg}...`;
  try {
    const p = await fetchJSON(`/api/index/data?symbol=${encodeURIComponent(symbol)}&freq=${freq}&days=${_state.currentDays}&agg=${_state.currentAgg}`);
    if (!charts.kl) charts.kl = echarts.init($('chart'), null, { renderer: 'canvas' });
    charts.kl.setOption({
      ...KL_OPT,
      title: { text: `${p.symbol} · ${freq.toUpperCase()} · ${p.days}d/${p.agg}`, left: 'center',
        textStyle: { color: '#e2e8f0', fontSize: 13, fontWeight: 'normal' } },
      xAxis: { ...KL_OPT.xAxis, data: p.data.map(r => r.date) },
      series: [{ ...KL_OPT.series[0], data: p.data.map(r => [r.open, r.close, r.low, r.high]) }],
    }, true);
    $('status').textContent = `✅ ${p.count} 条 (${p.data[0]?.date || '-'} → ${p.data[p.data.length-1]?.date || '-'})`;
  } catch (e) {
    $('status').textContent = `❌ ${e.message}`;
  }
}

async function loadETF() {
  try {
    const data = await fetchJSON(`/api/etf/overview?days=${_state.currentDays}`);
    const tbody = $('etf-tbody');
    tbody.innerHTML = '';
    for (const code of data.codes) {
      const rt = data.realtime[code] || {};
      const ts = data.shares_timeseries[code] || [];
      const tr = document.createElement('tr');
      const pct = rt.pct_chg;
      const pctCls = pct > 0 ? 'up' : pct < 0 ? 'down' : 'flat';
      tr.innerHTML = `
        <td class="code">${code}</td>
        <td class="name">${rt.name || '-'}</td>
        <td>${fmtNum(rt.close, 3)}</td>
        <td class="${changeClass(rt.change)}">${fmtNum(rt.change, 3)}</td>
        <td class="${pctCls}">${pct > 0 ? '+' : ''}${fmtNum(pct, 2)}%</td>
        <td>${fmtNum(rt.amplitude, 2)}%</td>
        <td>${fmtNum(rt.turnover, 2)}%</td>
        <td>${fmtNum(rt.iopv, 3)}</td>
        <td>${fmtNum(rt.discount, 2)}%</td>
        <td>${fmtVol(rt.volume)}</td>
        <td>${fmtShares(rt.shares)}</td>
        <td class="spark"><div class="spark-mini"></div></td>
      `;
      tbody.appendChild(tr);
      const sparkEl = tr.querySelector('.spark-mini');
      const vals = ts.map(r => r.shares);
      const last = ts[ts.length - 1], first = ts[0];
      const color = last && first && last.shares >= first.shares ? '#ef4444' : '#22c55e';
      const inst = echarts.init(sparkEl, null, { renderer: 'canvas' });
      inst.setOption(sparkOption(vals, color));
    }
  } catch (e) {
    $('etf-tbody').innerHTML = `<tr><td colspan="12" style="text-align:center;color:#ef4444;">❌ ${e.message}</td></tr>`;
  }
}

$('load').addEventListener('click', loadKline);

// ===== region 4: tab-alerts ============================================
async function loadAlerts() {
  const onlyUnack = $('alerts-only-unack')?.checked;
  try {
    const { alerts } = await fetchJSON(`/api/alerts?only_unack=${onlyUnack}`);
    const host = $('alerts-list');
    if (!alerts.length) {
      host.innerHTML = '<div class="empty-state">无告警 ✓</div>';
      return;
    }
    host.innerHTML = alerts.map(a => `
      <div class="alert-row ${a.severity}">
        <span class="sev ${a.severity}">${a.severity === 'red' ? '严重' : '警告'}</span>
        <div style="flex:1;">
          <div style="color:#e2e8f0;font-size:13px;">${a.message}</div>
          <div style="color:#64748b;font-size:10px;margin-top:2px;">
            <code>${a.alert_type}</code> · ${a.source} · ${a.created_at}
          </div>
        </div>
        <button class="ack ${a.acknowledged ? 'done' : ''}" data-id="${a.id}" ${a.acknowledged ? 'disabled' : ''}>
          ${a.acknowledged ? '✓ 已确认' : '确认'}
        </button>
      </div>
    `).join('');
    host.querySelectorAll('button.ack:not(.done)').forEach(b => {
      b.addEventListener('click', async () => {
        try {
          await fetchJSON(`/api/alerts/${b.dataset.id}/ack`, { method: 'POST' });
          b.classList.add('done'); b.textContent = '✓ 已确认'; b.disabled = true;
        } catch (e) { alert(`确认失败: ${e.message}`); }
      });
    });
  } catch (e) {
    $('alerts-list').innerHTML = `<div class="status-banner err">❌ ${e.message}</div>`;
  }
}
$('alerts-check')?.addEventListener('click', async () => {
  try {
    const data = await fetchJSON('/api/alerts/check', { method: 'POST' });
    alert(`检查完成: 触发 ${data.triggered || 0} 条告警`);
    loadAlerts();
  } catch (e) { alert(`失败: ${e.message}`); }
});
$('alerts-only-unack')?.addEventListener('change', loadAlerts);

// ===== region 5: tab-settings (cache / etf / index / stock) ===========
async function renderCacheStatus() {
  const tbody = $('cache-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="empty-state">加载中...</td></tr>';
  try {
    const data = await fetchJSON('/api/cache/status');
    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">暂无缓存数据</td></tr>';
      return;
    }
    tbody.innerHTML = data.items.map(it => {
      const statusCls = it.status === 'success' ? 'up' : it.status === 'stale' ? 'flat' : 'down';
      const statusLabel = {success: '✓ 正常', stale: '⏰ 过期', never: '⊘ 无数据', failed: '✗ 失败'}[it.status] || it.status;
      return `
        <tr>
          <td class="name"><code>${it.key}</code> <span style="color:#64748b;font-size:10px;">${it.scope}</span></td>
          <td><span class="change ${statusCls}">${statusLabel}</span></td>
          <td style="color:#94a3b8;font-size:11px;">${it.last_success || '-'}</td>
          <td style="color:#94a3b8;">${it.ttl_seconds}</td>
          <td>${it.row_count}</td>
          <td><button onclick="clearCache('${it.scope}', '${it.key}')">清</button></td>
        </tr>
      `;
    }).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state" style="color:#ef4444;">❌ ${e.message}</td></tr>`;
  }
}
async function clearCache(scope, key) {
  if (!confirm(`确认清空 ${scope}/${key}?`)) return;
  try {
    const data = await fetchJSON('/api/cache/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, key }),
    });
    alert(`已删除 ${data.deleted} 行`);
    renderCacheStatus();
  } catch (e) { alert(`失败: ${e.message}`); }
}

async function renderETFList() {
  const host = $('etf-pool-list');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const { etfs } = await fetchJSON('/api/etf/list');
    if (!etfs.length) { host.innerHTML = '<div class="empty-state">空 — 添加 ETF 开始追踪</div>'; return; }
    host.innerHTML = etfs.map(e => `
      <div class="pool-row">
        <span class="code">${e.code}</span>
        <span class="name">${e.name || '-'}</span>
        <span class="actions">
          <button class="danger" onclick="removeETF('${e.code}')">删除</button>
        </span>
      </div>
    `).join('');
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function searchETF() {
  const q = $('etf-search-q').value;
  const host = $('etf-search-results');
  host.style.display = 'block';
  host.innerHTML = '<div class="empty-state">搜索中...</div>';
  try {
    const { results } = await fetchJSON(`/api/etf/search?q=${encodeURIComponent(q)}`);
    if (!results.length) { host.innerHTML = '<div class="empty-state">无结果</div>'; return; }
    host.innerHTML = results.map(r => `
      <div class="search-result-row" onclick="addETF('${r.code}', '${r.name.replace(/'/g, '')}')">
        <span class="code">${r.code}</span><span>${r.name}</span>
        <span style="margin-left:auto;color:#3b82f6;">+ 加入</span>
      </div>
    `).join('');
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function addETF(code, name) {
  try {
    await fetchJSON('/api/etf/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, name }),
    });
    alert(`✓ ${code} 已加入 ETF 池`);
    renderETFList();
  } catch (e) { alert(`失败: ${e.message}`); }
}
async function removeETF(code) {
  if (!confirm(`从 ETF 池移除 ${code}?`)) return;
  try {
    await fetchJSON(`/api/etf/${code}`, { method: 'DELETE' });
    renderETFList();
  } catch (e) { alert(`失败: ${e.message}`); }
}

async function renderIndexList() {
  const host = $('index-pool-list');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const [{ indexes: cached }, { indexes: pool }] = await Promise.all([
      fetchJSON('/api/index/cache/list'),
      fetchJSON('/api/index/pool/list'),
    ]);
    const poolMap = new Map(pool.map(p => [p.symbol, p]));
    const symbols = new Set([...poolMap.keys(), ...cached.map(c => c.symbol)]);
    if (!symbols.size) { host.innerHTML = '<div class="empty-state">空 — 添加指数开始追踪</div>'; return; }
    host.innerHTML = [...symbols].map(sym => {
      const c = cached.find(x => x.symbol === sym) || {};
      const p = poolMap.get(sym);
      return `
        <div class="pool-row">
          <span class="code">${sym}</span>
          <span class="name">${p?.name || '-'} <span style="color:#64748b;font-size:10px;">d:${c.min_date||'-'}→${c.max_date||'-'} (${c.n||0})</span></span>
          <span class="actions">
            <button onclick="backfillIndex('${sym}')">回填</button>
            <button onclick="refreshIndex('${sym}')">刷新</button>
            <button class="danger" onclick="removeIndex('${sym}')">删</button>
          </span>
        </div>
      `;
    }).join('');
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function addIndex() {
  const symbol = $('index-add-symbol').value.trim();
  const name = $('index-add-name').value.trim();
  if (!symbol) { alert('symbol 必填'); return; }
  try {
    await fetchJSON('/api/index/pool/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, name }),
    });
    openProgressModal(`回填 ${symbol}`);
    const data = await fetchJSON('/api/cache/backfill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, freq: 'd', days: 365 }),
    });
    _appendLog(`✓ 写入 ${data.n_written} 行`, 'ok');
    alert(`${symbol} 已加入 + 回填 ${data.n_written} 条`);
    $('index-add-symbol').value = ''; $('index-add-name').value = '';
    renderIndexList();
  } catch (e) { alert(`失败: ${e.message}`); closeProgressModal(); }
}
async function refreshIndex(symbol) {
  openProgressModal(`刷新 ${symbol}`);
  try {
    const data = await fetchJSON('/api/cache/index/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    _appendLog(`✓ ${symbol} 返回 ${data.count} 条`, 'ok');
  } catch (e) { _appendLog(`✗ ${e.message}`, 'err'); }
}
async function backfillIndex(symbol) {
  openProgressModal(`回填 ${symbol}`);
  try {
    const data = await fetchJSON('/api/cache/backfill', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, freq: 'd', days: 365 }),
    });
    _appendLog(`✓ 写入 ${data.n_written} 行`, 'ok');
    alert(`回填完成: ${data.n_written} 行`);
    renderIndexList();
  } catch (e) { _appendLog(`✗ ${e.message}`, 'err'); alert(`失败: ${e.message}`); }
}
async function removeIndex(symbol) {
  if (!confirm(`删除 ${symbol} 池 + 缓存?`)) return;
  try {
    await fetchJSON('/api/index/cache/remove', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol }),
    });
    renderIndexList();
  } catch (e) { alert(`失败: ${e.message}`); }
}

async function renderStockList() {
  const host = $('stock-pool-list');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const { stocks } = await fetchJSON('/api/stock/list');
    if (!stocks.length) { host.innerHTML = '<div class="empty-state">空 — 添加自选股开始追踪</div>'; return; }
    host.innerHTML = stocks.map(s => `
      <div class="pool-row">
        <span class="code">${s.code}</span>
        <span class="name">${s.name || '-'}</span>
        <span class="actions">
          <button onclick="openStockDetail('${s.code}')">详情</button>
          <button class="danger" onclick="removeStock('${s.code}')">删除</button>
        </span>
      </div>
    `).join('');
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function searchStock() {
  const q = $('stock-search-q').value;
  const host = $('stock-search-results');
  host.style.display = 'block';
  host.innerHTML = '<div class="empty-state">搜索中...</div>';
  try {
    const { results } = await fetchJSON(`/api/stock/search?q=${encodeURIComponent(q)}`);
    if (!results.length) { host.innerHTML = '<div class="empty-state">无结果</div>'; return; }
    host.innerHTML = results.map(r => `
      <div class="search-result-row" onclick="addStock('${r.code}', '${r.name.replace(/'/g, '')}')">
        <span class="code">${r.code}</span><span>${r.name}</span>
        <span style="margin-left:auto;color:#3b82f6;">+ 加入</span>
      </div>
    `).join('');
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function addStock(code, name) {
  try {
    await fetchJSON('/api/stock/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, name }),
    });
    alert(`✓ ${code} 已加入自选股`);
    renderStockList();
  } catch (e) { alert(`失败: ${e.message}`); }
}
async function removeStock(code) {
  if (!confirm(`从自选股移除 ${code}?`)) return;
  try {
    await fetchJSON(`/api/stock/${code}`, { method: 'DELETE' });
    renderStockList();
  } catch (e) { alert(`失败: ${e.message}`); }
}

// ===== region 6: tab-settings (jobs + cron drawer) =====================
async function renderJobList() {
  const host = $('jobs-list');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const { jobs } = await fetchJSON('/api/jobs');
    host.innerHTML = `
      <div class="job-row" style="background:rgba(255,255,255,0.04);font-weight:500;color:#94a3b8;">
        <span>JOB</span><span>层</span><span>CRON</span><span>说明</span><span>最近状态</span><span>最近运行</span><span>操作</span>
      </div>
      ${jobs.map(j => {
        const status = j.last_status || 'none';
        const last = j.last_run_at ? j.last_run_at.replace('T', ' ').slice(0, 16) : '-';
        return `
          <div class="job-row">
            <span class="job-id">${j.job_id}</span>
            <span class="layer">${j.layer}</span>
            <span class="cron">${j.cron_expr}</span>
            <span style="color:#94a3b8;">${j.description || ''}</span>
            <span class="status ${status}">${status === 'success' ? '✓ 成功' : status === 'failed' ? '✗ 失败' : '— 未跑'}</span>
            <span style="color:#64748b;font-size:11px;">${last}</span>
            <span>
              <button onclick="triggerJob('${j.job_id}')">▶ 触发</button>
              <button onclick="openEditJobDrawer('${j.job_id}', '${j.cron_expr}')">✏</button>
              <button onclick="renderJobLog('${j.job_id}')">📜</button>
            </span>
          </div>
        `;
      }).join('')}
    `;
  } catch (e) { host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`; }
}
async function triggerJob(jobId) {
  openProgressModal(`触发 ${jobId}`);
  try {
    const data = await fetchJSON(`/api/jobs/${jobId}/trigger`, { method: 'POST' });
    _appendLog(`✓ ${data.result}`, 'ok');
    renderJobList();
  } catch (e) { _appendLog(`✗ ${e.message}`, 'err'); alert(`失败: ${e.message}`); }
}
function _fillCronSelect(sel, start, end) {
  sel.innerHTML = '';
  for (let i = start; i <= end; i++) {
    const o = document.createElement('option');
    o.value = String(i); o.textContent = String(i);
    sel.appendChild(o);
  }
}
function _fillDowSelect(sel) {
  sel.innerHTML = '';
  const labels = ['周日(0)', '周一(1)', '周二(2)', '周三(3)', '周四(4)', '周五(5)', '周六(6)'];
  labels.forEach((l, i) => {
    const o = document.createElement('option');
    o.value = String(i); o.textContent = l;
    sel.appendChild(o);
  });
}
function _parseCron(cron) {
  // cron: 分 时 日 月 星期
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return null;
  return { min: parts[0], hour: parts[1], dom: parts[2], month: parts[3], dow: parts[4] };
}
function _buildCron() {
  const min = $('cron-min').value || '0';
  const hour = $('cron-hour').value || '*';
  const dom = $('cron-dom').value || '*';
  const month = $('cron-month').value || '*';
  const dow = Array.from($('cron-dow').selectedOptions).map(o => o.value).join(',') || '*';
  return `${min} ${hour} ${dom} ${month} ${dow}`;
}
function _setSelectValue(sel, val) {
  if (val === '*') {
    Array.from(sel.options).forEach(o => o.selected = true);
    return;
  }
  const vals = String(val).split(',');
  Array.from(sel.options).forEach(o => o.selected = vals.includes(o.value));
}
function _cronPreviewNL(cron) {
  const parts = cron.split(/\s+/);
  if (parts.length !== 5) return cron;
  const [min, hour, dom, month, dow] = parts;
  let s = '';
  // 星期描述
  const dowDesc = (d) => {
    if (d === '*') return '每天';
    if (d === '1-5') return '每个工作日';
    if (d === '6,0' || d === '0,6') return '周末';
    const map = ['周日','周一','周二','周三','周四','周五','周六'];
    const days = d.split(',').map(x => map[parseInt(x)] || x).join(',');
    return days;
  };
  // 时间
  const timeStr = hour === '*' ? `每分钟` : min === '0' ? `${hour}:00` : `${hour}:${min.padStart(2,'0')}`;
  // 日 / 月
  const dateDesc = dom === '*' && month === '*' ? '' : `${dom === '*' ? '每天' : `${dom}日`} ${month === '*' ? '每月' : `${month}月`}`;
  s += `${dowDesc(dow)} ${timeStr}`;
  if (dateDesc) s += ` (${dateDesc})`;
  return s;
}
function _updateCronPreview() {
  try {
    const cron = _buildCron();
    $('cron-preview').textContent = `${cron} → ${_cronPreviewNL(cron)}`;
  } catch (e) { $('cron-preview').textContent = e.message; }
}
function openEditJobDrawer(jobId, cron) {
  _state.editingJobId = jobId;
  $('cron-job-id').textContent = jobId;
  $('drawer-backdrop').classList.add('open');
  $('cron-drawer').classList.add('open');
  _fillCronSelect($('cron-min'), 0, 59);
  _fillCronSelect($('cron-hour'), 0, 23);
  _fillCronSelect($('cron-dom'), 1, 31);
  _fillCronSelect($('cron-month'), 1, 12);
  _fillDowSelect($('cron-dow'));
  const parsed = _parseCron(cron);
  if (parsed) {
    _setSelectValue($('cron-min'), parsed.min);
    _setSelectValue($('cron-hour'), parsed.hour);
    _setSelectValue($('cron-dom'), parsed.dom);
    _setSelectValue($('cron-month'), parsed.month);
    _setSelectValue($('cron-dow'), parsed.dow);
  }
  $('cron-min').onchange = $('cron-hour').onchange = $('cron-dom').onchange =
  $('cron-month').onchange = $('cron-dow').onchange = _updateCronPreview;
  _updateCronPreview();
}
function closeDrawer() {
  $('drawer-backdrop').classList.remove('open');
  $('cron-drawer').classList.remove('open');
  _state.editingJobId = null;
}
async function saveJobEdit() {
  const cron = _buildCron();
  const jobId = _state.editingJobId;
  if (!jobId) { closeDrawer(); return; }
  try {
    await fetchJSON(`/api/jobs/${jobId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cron_expr: cron }),
    });
    alert(`✓ ${jobId} cron 已更新为 ${cron}`);
    closeDrawer();
    renderJobList();
  } catch (e) {
    alert(`保存失败: ${e.message}`);
  }
}

async function renderJobLog(jobId) {
  const host = $('job-log-host');
  host.innerHTML = '<div class="empty-state">加载历史日志...</div>';
  try {
    const { logs } = await fetchJSON(`/api/jobs/${jobId}/log?limit=10`);
    if (!logs || !logs.length) {
      host.innerHTML = `<div class="empty-state">${jobId} 暂无运行记录</div>`;
      return;
    }
    host.innerHTML = `
      <div class="card" style="background:rgba(255,255,255,0.02);padding:12px;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:8px;">📜 ${jobId} 最近 ${logs.length} 条运行</div>
        <div style="font-family:monospace;font-size:11px;">
          ${logs.map(e => {
            const cls = e.status === 'success' ? 'color:#86efac' : e.status === 'failed' ? 'color:#fca5a5' : 'color:#94a3b8';
            const ts = `${e.date || '-'} ${(e.completed_at || '').slice(11, 19)}`;
            return `<div style="${cls};padding:2px 0;">[${ts}] ${e.status || '-'} (${e.task_id})</div>`;
          }).join('')}
        </div>
      </div>
    `;
  } catch (e) {
    host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`;
  }
}

// ===== region 7: tab-stocks ===========================================
async function loadStocks() {
  const host = $('stock-list-host');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const { stocks } = await fetchJSON('/api/stock/list');
    if (!stocks.length) {
      host.innerHTML = '<div class="empty-state">空 — 切到 "数据管理" → 自选股 添加</div>';
      return;
    }
    host.innerHTML = stocks.map(s => `
      <div class="pool-row">
        <span class="code">${s.code}</span>
        <span class="name">${s.name || '-'}</span>
        <span class="actions">
          <button onclick="openStockDetail('${s.code}')">详情</button>
          <button class="danger" onclick="removeStock('${s.code}'); loadStocks();">删除</button>
        </span>
      </div>
    `).join('');
  } catch (e) {
    host.innerHTML = `<div class="empty-state" style="color:#ef4444;">❌ ${e.message}</div>`;
  }
}
async function openStockDetail(code) {
  const host = $('stock-detail-host');
  host.innerHTML = '<div class="empty-state">加载中...</div>';
  try {
    const [summary, fundflow, news, kline] = await Promise.all([
      fetchJSON(`/api/stock/${code}/summary`).catch(() => ({})),
      fetchJSON(`/api/stock/${code}/fund_flow`).catch(() => ({ rows: [] })),
      fetchJSON(`/api/stock/${code}/news?limit=5`).catch(() => ({ news: [] })),
      fetchJSON(`/api/stock/${code}/kline?freq=d&limit=60`).catch(() => ({ data: [] })),
    ]);
    const s = summary || {};
    const ff = (fundflow.rows || [])[0] || {};
    host.innerHTML = `
      <div class="stock-detail">
        <h3 style="margin:0 0 8px 0;color:#fff;">${s.name || code} <code style="color:#64748b;">${code}</code></h3>
        <div class="meta">
          <div class="item"><div class="label">现价</div><div class="value">${fmtNum(s.close, 2)}</div></div>
          <div class="item"><div class="label">涨跌</div><div class="value ${changeClass(s.change)}">${fmtPct(s.change_pct)}</div></div>
          <div class="item"><div class="label">成交量</div><div class="value">${fmtVol(s.volume)}</div></div>
          <div class="item"><div class="label">换手率</div><div class="value">${fmtNum(s.turnover_rate, 2)}%</div></div>
          <div class="item"><div class="label">市盈率</div><div class="value">${fmtNum(s.pe, 2)}</div></div>
          <div class="item"><div class="label">市净率</div><div class="value">${fmtNum(s.pb, 2)}</div></div>
          <div class="item"><div class="label">总市值</div><div class="value">${fmtVol(s.market_cap)}</div></div>
          <div class="item"><div class="label">流通市值</div><div class="value">${fmtVol(s.float_cap)}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
          <div>
            <div style="color:#94a3b8;font-size:11px;margin-bottom:6px;">K线</div>
            <div id="stock-kline" style="height:240px;background:rgba(255,255,255,0.02);border-radius:6px;"></div>
          </div>
          <div>
            <div style="color:#94a3b8;font-size:11px;margin-bottom:6px;">主力资金流</div>
            <div class="meta" style="grid-template-columns:1fr 1fr;">
              <div class="item"><div class="label">主力净额</div><div class="value ${changeClass(ff.main_net_inflow)}">${fmtVol(ff.main_net_inflow)}</div></div>
              <div class="item"><div class="label">超大单</div><div class="value ${changeClass(ff.super_net_inflow)}">${fmtVol(ff.super_net_inflow)}</div></div>
              <div class="item"><div class="label">大单</div><div class="value ${changeClass(ff.big_net_inflow)}">${fmtVol(ff.big_net_inflow)}</div></div>
              <div class="item"><div class="label">中单</div><div class="value ${changeClass(ff.medium_net_inflow)}">${fmtVol(ff.medium_net_inflow)}</div></div>
            </div>
          </div>
        </div>
        <div class="news-list">
          <div style="color:#94a3b8;font-size:11px;margin-bottom:6px;">最近新闻 (${(news.news || []).length})</div>
          ${(news.news || []).map(n => `
            <div class="news-item">
              <a href="${n.url}" target="_blank">${n.title}</a>
              <div class="meta">${n.source} · ${n.time}</div>
            </div>
          `).join('') || '<div class="empty-state" style="padding:12px;">无新闻</div>'}
        </div>
      </div>
    `;
    // render kline
    if (kline.data && kline.data.length) {
      const klEl = $('stock-kline');
      if (charts.stockKl) charts.stockKl.dispose();
      charts.stockKl = echarts.init(klEl, null, { renderer: 'canvas' });
      charts.stockKl.setOption({
        ...KL_OPT,
        title: undefined,
        grid: { top: 10, right: 10, bottom: 30, left: 50 },
        xAxis: { ...KL_OPT.xAxis, data: kline.data.map(r => r.date) },
        series: [{ ...KL_OPT.series[0], data: kline.data.map(r => [r.open, r.close, r.low, r.high]) }],
      }, true);
    } else {
      $('stock-kline').innerHTML = '<div class="empty-state" style="padding-top:80px;">无 K线数据</div>';
    }
  } catch (e) {
    host.innerHTML = `<div class="status-banner err">❌ ${e.message}</div>`;
  }
}

// ===== region 8: boot =================================================
window.addEventListener('resize', () => {
  if (charts.kl) charts.kl.resize();
  if (charts.stockKl) charts.stockKl.resize();
});

document.addEventListener('DOMContentLoaded', () => {
  // restore period/agg from localStorage
  const savedDays = parseInt(localStorage.getItem('currentDays') || '30', 10);
  const savedAgg = localStorage.getItem('currentAgg') || 'day';
  setDays(savedDays, document.querySelector(`.period-btn[data-days="${savedDays}"]`));
  setAgg(savedAgg, document.querySelector(`.agg-btn[data-agg="${savedAgg}"]`));
  const savedTab = localStorage.getItem('activeTab') || 'dashboard';
  switchTab(savedTab);
  _initWS();
});