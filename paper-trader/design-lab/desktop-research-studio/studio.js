'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const rows = window.NIFTY_HISTORY;
const state = {symbol: 'NIFTY 50', range: 63, line: false, selectedRule: null, preview: false, fresh: false};
const layoutKey = 'strategy-os.desktop-studio.layout.v1';
const workspace = $('#workspace');
const layout = readLayout();
let graphNodes = [];
let graphEdges = [];
let nodeSequence = 0;
let graphZoom = 1;
let graphPan = {x: 0, y: 0};
let graphSpaceHeld = false;
let pendingConnection = null;
let chart;
let candles;
let closeSeries;
let averageSeries;
let lastRange = null;
let toastTimer;

function readLayout() {
  try {
    const saved = JSON.parse(localStorage.getItem(layoutKey));
    return {left: finiteOr(saved?.left, 292), top: finiteOr(saved?.top, 0)};
  } catch { return {left: 292, top: 0}; }
}
function finiteOr(value, fallback) { return typeof value === 'number' && Number.isFinite(value) ? value : fallback; }
function clamp(value, minimum, maximum) { return Math.max(minimum, Math.min(maximum, value)); }
function bounds(axis) {
  if (axis === 'left') return [240, Math.max(240, Math.min(560, workspace.clientWidth - 24 - 9 - 480))];
  return [280, Math.max(280, workspace.clientHeight - 12 - 9 - 250)];
}
function persistLayout() {
  try { localStorage.setItem(layoutKey, JSON.stringify({left: layout.left, top: layout.top})); }
  catch { announce('Layout changed for this session. Browser storage is unavailable.'); }
}
function applyLayout(save = false) {
  for (const axis of ['left', 'top']) {
    const [minimum, maximum] = bounds(axis);
    const proposed = axis === 'top' && !layout.top ? workspace.clientHeight * .57 : layout[axis];
    layout[axis] = clamp(proposed, minimum, maximum);
    workspace.style.setProperty(`--${axis}`, `${layout[axis]}px`);
    const divider = $(axis === 'left' ? '#vertical-divider' : '#horizontal-divider');
    divider.setAttribute('aria-valuemin', minimum);
    divider.setAttribute('aria-valuemax', maximum);
    divider.setAttribute('aria-valuenow', Math.round(layout[axis]));
    divider.setAttribute('aria-valuetext', `${Math.round(layout[axis])} pixels`);
  }
  if (save) persistLayout();
}
function resetLayout() {
  layout.left = 292; layout.top = 0;
  restorePanes(); applyLayout(true); announce('Workspace layout reset. Strategy rules are unchanged.');
}
function installDivider(selector, axis) {
  const divider = $(selector);
  let drag = null;
  divider.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    drag = {position: axis === 'left' ? event.clientX : event.clientY, value: layout[axis]};
    divider.setPointerCapture(event.pointerId); divider.classList.add('dragging'); document.body.classList.add('resizing');
    event.preventDefault();
  });
  divider.addEventListener('pointermove', (event) => {
    if (!drag) return;
    const position = axis === 'left' ? event.clientX : event.clientY;
    layout[axis] = drag.value + position - drag.position; applyLayout();
  });
  const finish = () => { if (!drag) return; drag = null; divider.classList.remove('dragging'); document.body.classList.remove('resizing'); persistLayout(); };
  divider.addEventListener('pointerup', finish); divider.addEventListener('pointercancel', finish); divider.addEventListener('lostpointercapture', finish);
  divider.addEventListener('keydown', (event) => resizeByKey(event, axis));
}
function resizeByKey(event, axis) {
  const keys = axis === 'left' ? ['ArrowLeft', 'ArrowRight'] : ['ArrowUp', 'ArrowDown'];
  const step = event.shiftKey ? 32 : 8;
  const values = {[keys[0]]: layout[axis] - step, [keys[1]]: layout[axis] + step, Home: bounds(axis)[0], End: bounds(axis)[1]};
  if (!(event.key in values)) return;
  event.preventDefault(); layout[axis] = values[event.key]; applyLayout(true);
}
function restorePanes() {
  delete workspace.dataset.expanded; $('#restore-layout').hidden = true;
  $$('[data-expand]').forEach((button) => { button.setAttribute('aria-label', `Expand ${button.dataset.expand}`); button.title = `Expand ${button.dataset.expand}`; });
}
function expandPane(name) {
  if (workspace.dataset.expanded === name) { restorePanes(); return; }
  restorePanes(); workspace.dataset.expanded = name; $('#restore-layout').hidden = false;
  const button = $(`[data-expand="${name}"]`); button.setAttribute('aria-label', `Restore ${name}`); button.title = 'Restore layout';
  announce(`${name === 'chart' ? 'Chart' : name === 'watch' ? 'Watchlist' : 'Builder'} expanded. Press Escape to restore.`);
}
function announce(message) {
  clearTimeout(toastTimer); $('#toast').textContent = message; $('#toast').classList.add('visible');
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3600);
}
function number(value) { return value.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
function dateLabel(value) { return new Date(`${value}T12:00:00Z`).toLocaleDateString('en-GB', {day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC'}); }
function ema(values, period) {
  const output = Array(values.length).fill(null);
  if (values.length < period) return output;
  output[period - 1] = values.slice(0, period).reduce((sum, row) => sum + row[4], 0) / period;
  for (let i = period; i < values.length; i++) output[i] = values[i][4] * (2 / (period + 1)) + output[i - 1] * (1 - 2 / (period + 1));
  return output;
}
const movingAverage = ema(rows, 50);
function showOhlc(row) {
  $('#ohlc').innerHTML = `<span>${dateLabel(row[0])}</span>` + ['O', 'H', 'L', 'C'].map((field, i) => `<span>${field}<b>${number(row[i + 1])}</b></span>`).join('');
}
function chartDate(time) {
  if (typeof time === 'string') return time;
  if (typeof time === 'number') return new Date(time * 1000).toISOString().slice(0, 10);
  return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`;
}
function setupChart() {
  const host = $('#price-chart');
  chart = LightweightCharts.createChart(host, {
    width: host.clientWidth || 800, height: host.clientHeight || 320,
    layout: {background: {color: '#17191c'}, textColor: '#a2a7ae', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: 11, attributionLogo: true},
    grid: {vertLines: {color: '#222529'}, horzLines: {color: '#222529'}},
    rightPriceScale: {borderColor: '#34373c', scaleMargins: {top: .13, bottom: .12}},
    timeScale: {borderColor: '#34373c', rightOffset: 3, barSpacing: 8, timeVisible: false},
    crosshair: {mode: LightweightCharts.CrosshairMode.Normal},
    handleScroll: {mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true},
    handleScale: {axisPressedMouseMove: {time: true, price: true}, axisDoubleClickReset: true, mouseWheel: true, pinch: true},
  });
  candles = chart.addCandlestickSeries({upColor: '#73b5a2', downColor: '#d78784', borderVisible: false, wickUpColor: '#73b5a2', wickDownColor: '#d78784'});
  closeSeries = chart.addLineSeries({color: '#b0b8c8', lineWidth: 2, visible: false});
  averageSeries = chart.addLineSeries({color: '#bdaa81', lineWidth: 1, priceLineVisible: false, lastValueVisible: false});
  candles.setData(rows.map(([time, open, high, low, close]) => ({time, open, high, low, close})));
  closeSeries.setData(rows.map(([time, , , , value]) => ({time, value})));
  averageSeries.setData(rows.flatMap(([time], i) => movingAverage[i] === null ? [] : [{time, value: movingAverage[i]}]));
  chart.subscribeCrosshairMove((event) => {
    if (!event.time) { showOhlc(rows.at(-1)); return; }
    const time = chartDate(event.time);
    const row = rows.find((item) => item[0] === time);
    if (row) showOhlc(row);
  });
  chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
    if (range && state.symbol === 'NIFTY 50') $('#date-range').textContent = `${dateLabel(chartDate(range.from))} — ${dateLabel(chartDate(range.to))}`;
  });
  new ResizeObserver(() => {
    if (!host.clientWidth || !host.clientHeight) return;
    const range = chart.timeScale().getVisibleLogicalRange();
    chart.resize(host.clientWidth, host.clientHeight, true);
    if (range) chart.timeScale().setVisibleLogicalRange(range);
  }).observe(host);
}
function renderChart() {
  if (!chart) setupChart();
  const empty = state.symbol !== 'NIFTY 50';
  $('#chart-symbol').textContent = state.symbol; $('#chart-empty').hidden = !empty; $('#price-chart').style.visibility = empty ? 'hidden' : 'visible';
  if (empty) { $('#ohlc').textContent = 'No attached price history'; $('#date-range').textContent = 'No dataset'; return; }
  candles.applyOptions({visible: !state.line}); closeSeries.applyOptions({visible: state.line});
  averageSeries.applyOptions({lineWidth: state.selectedRule === 'trend' ? 2 : 1});
  if (lastRange !== state.range) {
    chart.timeScale().setVisibleLogicalRange({from: rows.length - state.range, to: rows.length + 2});
    lastRange = state.range;
  }
  const visible = rows.slice(-state.range);
  $('#date-range').textContent = `${dateLabel(visible[0][0])} — ${dateLabel(rows.at(-1)[0])}`;
  $('#chart-summary').textContent = `NIFTY 50, 248 recorded daily OHLC rows. Pan or zoom the chart and inspect individual candles. Last recorded close ${number(rows.at(-1)[4])}. EMA is a chart guide only.`;
  showOhlc(rows.at(-1));
}
function selectInstrument(symbol) {
  state.symbol = symbol;
  $$('[data-symbol]').forEach((button) => { const active = button.dataset.symbol === symbol; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', active); });
  setChartTab('price'); renderChart();
}
function setChartTab(name) {
  $('#price-view').hidden = name !== 'price'; $('#results-view').hidden = name !== 'results';
  $$('[data-chart-tab]').forEach((button) => { const active = button.dataset.chartTab === name; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', active); });
}
function setWatchTab(name) {
  $('#watchlist-view').hidden = name !== 'watchlist'; $('#runs-view').hidden = name !== 'runs';
  $$('[data-watch]').forEach((button) => { const active = button.dataset.watch === name; button.classList.toggle('selected', active); button.setAttribute('aria-pressed', active); });
}
const componentTypes = {
  data: {family: 4, name: 'Price series', detail: 'NIFTY 50 · 1D', input: false, fields: {}, info: 'NIFTY 50 daily OHLC. Volume is absent. Benchmark input only.'},
  average: {family: 2, name: 'Moving average', detail: 'EMA · 50 bars', fields: {Period: 50}, info: 'Exponential moving average of completed closes. The chart guide uses the recorded history.'},
  trend: {family: 2, name: 'EMA slope', detail: 'Above 0', fields: {Threshold: 0}, info: 'Compare the change in the moving average with a threshold.'},
  momentum: {family: 2, name: 'Z-score', detail: 'Above 0', fields: {Period: 20, Threshold: 0}, info: 'Standardized price distance with an editable lookback and threshold.'},
  all: {family: 5, name: 'All conditions', detail: 'Match every input', fields: {}, info: 'Combine the connected conditions.'},
  exit: {family: 5, name: 'Exit condition', detail: 'Slope below 0', fields: {Threshold: 0}, info: 'Observe a negative slope. No order or position is connected.'},
  range: {family: 3, name: 'Range filter', detail: 'Daily range', fields: {Period: 20, Threshold: 0}, info: 'Compare the recorded high-low range with a threshold.'},
  breakout: {family: 3, name: 'Price breakout', detail: 'Prior high · 20 bars', fields: {Period: 20}, info: 'Compare completed close with the previous recorded bars’ high.'},
};
function safe(value) { return String(value).replace(/[&<>"']/g, (character) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character])); }
function makeNode(type, x, y) {
  const component = componentTypes[type];
  return {id: `node-${++nodeSequence}`, type, name: component.name, fields: {...component.fields}, x, y};
}
function resetGraph(breakout = false) {
  pendingConnection = null;
  graphNodes = [makeNode('data', 45, 145), makeNode('average', 295, 55), makeNode(breakout ? 'breakout' : 'trend', 550, 55), makeNode('momentum', 295, 235), makeNode('all', 810, 140), makeNode('exit', 1070, 140)];
  const [data, average, trend, momentum, all, exit] = graphNodes;
  graphEdges = [[data.id, average.id], [average.id, trend.id], [data.id, momentum.id], [trend.id, all.id], [momentum.id, all.id], [all.id, exit.id]];
  state.fresh = false; renderGraph();
}
function nodeDetail(node) {
  if (!Object.keys(node.fields).length) return componentTypes[node.type].detail;
  return Object.entries(node.fields).map(([name, value]) => `${name} ${value}`).join(' · ');
}
function renderGraph() {
  $('#fresh-builder').hidden = graphNodes.length !== 0;
  $('#graph-nodes').innerHTML = graphNodes.map((node) => `<article class="graph-node${state.selectedNode === node.id ? ' selected' : ''}" data-node="${node.id}" data-node-family="TYPE_${componentTypes[node.type].family}" style="left:${node.x}px;top:${node.y}px" tabindex="0" aria-label="${safe(node.name)} component"><div class="node-title"><span class="node-type-mark">${node.type === 'data' ? '↗' : node.type === 'all' ? '∧' : 'ƒ'}</span><strong>${safe(node.name)}</strong><span class="node-family-label">Type ${componentTypes[node.type].family}</span></div><div class="node-detail">${safe(nodeDetail(node))}</div>${componentTypes[node.type].input === false ? '' : `<button class="port input" data-port="input" aria-label="Connect input of ${safe(node.name)}" title="Input"></button>`}<button class="port output" data-port="output" aria-label="Connect output of ${safe(node.name)}" title="Output"></button></article>`).join('');
  drawEdges();
}
function drawEdges() {
  $('#graph-edges').innerHTML = graphEdges.map(([source, target]) => {
    const from = graphNodes.find((node) => node.id === source), to = graphNodes.find((node) => node.id === target);
    if (!from || !to) return '';
    const x = from.x + 190, y = from.y + 43, tx = to.x, ty = to.y + 43;
    return `<path d="M${x},${y} C${x + 55},${y} ${tx - 55},${ty} ${tx},${ty}" class="${state.selectedNode === source || state.selectedNode === target ? 'selected' : ''}"/>`;
  }).join('');
}
function inspectRule(id) {
  const node = graphNodes.find((item) => item.id === id); if (!node) return;
  pendingConnection = null; state.selectedNode = id; state.selectedRule = node.type === 'average' || node.type === 'trend' ? 'trend' : null;
  $('#inspector-title').textContent = node.name; $('#node-name').value = node.name;
  $('#inspector-description').textContent = componentTypes[node.type].info;
  $('#component-parameters').innerHTML = Object.entries(node.fields).map(([name, value]) => `<label>${name}<input type="number" data-field="${name}" value="${value}" ${name === 'Period' ? 'min="1" max="1000" step="1"' : 'step="0.1"'} required></label>`).join('') + `<div class="node-connections">${graphEdges.filter(([from, to]) => from === id || to === id).map(([from, to]) => `<button type="button" data-disconnect="${from}:${to}">Disconnect ${safe(graphNodes.find((n) => n.id === (from === id ? to : from)).name)}</button>`).join('')}</div>`;
  $('#selected-guide').hidden = state.selectedRule !== 'trend'; $('#inspector').hidden = false;
  renderGraph(); renderChart();
}
function closeInspector() {
  const previous = state.selectedNode; pendingConnection = null; state.selectedNode = null; state.selectedRule = null;
  $('#inspector').hidden = true; $('#selected-guide').hidden = true; renderGraph(); renderChart();
  $(`[data-node="${previous}"]`)?.focus();
}
function applyRule(event) {
  event.preventDefault(); const node = graphNodes.find((item) => item.id === state.selectedNode); if (!node) return;
  const name = $('#node-name').value.trim(); if (!name) return;
  node.name = name;
  $$('[data-field]').forEach((input) => { node.fields[input.dataset.field] = Number(input.value); });
  renderGraph(); $('#inspector-title').textContent = name;
}
function removeNode() {
  const id = state.selectedNode;
  graphNodes = graphNodes.filter((node) => node.id !== id); graphEdges = graphEdges.filter((edge) => !edge.includes(id));
  closeInspector();
}
function connectPort(button) {
  const id = button.closest('[data-node]').dataset.node;
  if (button.dataset.port === 'output') {
    pendingConnection = id; $$('[data-port]').forEach((port) => port.classList.remove('connecting')); button.classList.add('connecting'); return;
  }
  if (!pendingConnection || pendingConnection === id || !graphNodes.some((node) => node.id === pendingConnection)) return;
  if (!graphEdges.some(([from, to]) => from === pendingConnection && to === id)) graphEdges.push([pendingConnection, id]);
  pendingConnection = null; renderGraph(); if (state.selectedNode) inspectRule(state.selectedNode);
}
function setGraphZoom(value) {
  const viewport = $('#graph-viewport'), next = clamp(value, .35, 1.6), ratio = next / graphZoom;
  graphPan = {x: viewport.clientWidth / 2 - (viewport.clientWidth / 2 - graphPan.x) * ratio,
    y: viewport.clientHeight / 2 - (viewport.clientHeight / 2 - graphPan.y) * ratio};
  graphZoom = next; applyGraphViewport();
  $('#fit-graph').textContent = `${Math.round(graphZoom * 100)}%`;
}
function applyGraphViewport() {
  $('#rule-flow').style.transform = `translate(${graphPan.x}px, ${graphPan.y}px) scale(${graphZoom})`;
  $('#graph-viewport').style.backgroundPosition = `${graphPan.x}px ${graphPan.y}px`;
  $('#graph-viewport').style.backgroundSize = `${20 * graphZoom}px ${20 * graphZoom}px`;
}
function fitGraph() {
  const viewport = $('#graph-viewport');
  if (!graphNodes.length) { resetGraphViewport(); return; }
  const left = Math.min(...graphNodes.map((node) => node.x)) - 6, top = Math.min(...graphNodes.map((node) => node.y));
  const right = Math.max(...graphNodes.map((node) => node.x + 196)), bottom = Math.max(...graphNodes.map((node) => node.y + 86));
  graphZoom = Math.max(.01, Math.min(1.6, (viewport.clientWidth - 30) / (right - left), (viewport.clientHeight - 24) / (bottom - top)));
  graphPan = {x: (viewport.clientWidth - (right + left) * graphZoom) / 2, y: (viewport.clientHeight - (bottom + top) * graphZoom) / 2};
  applyGraphViewport(); $('#fit-graph').textContent = `${Math.round(graphZoom * 100)}%`;
}
function resetGraphViewport() {
  graphZoom = 1; graphPan = {x: 0, y: 0}; applyGraphViewport(); $('#fit-graph').textContent = '100%';
}
function graphViewportKey(event) {
  const moves = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
  if (event.key === 'Home') { event.preventDefault(); fitGraph(); return; }
  if (event.key === '0') { event.preventDefault(); resetGraphViewport(); return; }
  if (!moves[event.key]) return;
  event.preventDefault(); const [dx, dy] = moves[event.key], step = event.shiftKey ? 64 : 32;
  graphPan = {x: graphPan.x + dx * step, y: graphPan.y + dy * step}; applyGraphViewport();
}
function installGraphPanKeys(viewport) {
  document.addEventListener('keydown', (event) => {
    if (event.key !== ' ' || !viewport.contains(event.target) || event.target.closest('button,a,input,textarea,select,[contenteditable=true]')) return;
    graphSpaceHeld = true; viewport.classList.add('pan-ready');
    if (viewport.contains(event.target)) event.preventDefault();
  });
  const release = () => { graphSpaceHeld = false; viewport.classList.remove('pan-ready'); };
  document.addEventListener('keyup', (event) => { if (event.key === ' ') release(); });
  window.addEventListener('blur', release);
}
function installGraphEvents() {
  const viewport = $('#graph-viewport'); let drag = null; let moved = false;
  installGraphPanKeys(viewport);
  viewport.addEventListener('pointerdown', (event) => {
    const element = event.target.closest('[data-node]'); moved = false;
    if (event.button === 1 || (event.button === 0 && (graphSpaceHeld || !element))) {
      drag = {kind: 'pan', x: event.clientX, y: event.clientY, left: graphPan.x, top: graphPan.y};
      viewport.setPointerCapture(event.pointerId); viewport.classList.add('panning'); event.preventDefault();
      if (!element) viewport.focus(); return;
    }
    if (event.button !== 0 || event.target.closest('button')) return;
    const node = graphNodes.find((item) => item.id === element.dataset.node);
    drag = {kind: 'node', node, element, x: event.clientX, y: event.clientY, left: node.x, top: node.y};
    element.setPointerCapture(event.pointerId); event.preventDefault();
  });
  viewport.addEventListener('pointermove', (event) => {
    if (!drag) return;
    if (drag.kind === 'pan') {
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      moved ||= Math.abs(dx) + Math.abs(dy) > 3;
      graphPan = {x: drag.left + dx, y: drag.top + dy}; applyGraphViewport(); return;
    }
    const dx = (event.clientX - drag.x) / graphZoom, dy = (event.clientY - drag.y) / graphZoom;
    moved ||= Math.abs(dx) + Math.abs(dy) > 3;
    drag.node.x = clamp(drag.left + dx, 10, 1130); drag.node.y = clamp(drag.top + dy, 10, 650);
    drag.element.style.left = `${drag.node.x}px`; drag.element.style.top = `${drag.node.y}px`; drawEdges();
  });
  const finish = () => { drag = null; viewport.classList.remove('panning'); };
  viewport.addEventListener('pointerup', finish); viewport.addEventListener('pointercancel', finish); viewport.addEventListener('lostpointercapture', finish);
  window.addEventListener('blur', finish);
  viewport.addEventListener('click', (event) => {
    if (moved) { moved = false; return; }
    const port = event.target.closest('[data-port]'); if (port) { connectPort(port); return; }
    const node = event.target.closest('[data-node]'); if (node) inspectRule(node.dataset.node);
  });
  viewport.addEventListener('keydown', (event) => {
    if (event.target === viewport || graphSpaceHeld) { graphViewportKey(event); return; }
    const element = event.target.closest('[data-node]'); if (!element || event.target !== element) return;
    const node = graphNodes.find((item) => item.id === element.dataset.node);
    if (event.key === 'Enter') { inspectRule(node.id); return; }
    const moves = {ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1]};
    if (!moves[event.key]) return;
    event.preventDefault(); const [dx, dy] = moves[event.key], step = event.shiftKey ? 32 : 8;
    node.x = clamp(node.x + dx * step, 10, 1130); node.y = clamp(node.y + dy * step, 10, 650);
    renderGraph(); $(`[data-node="${node.id}"]`).focus();
  });
  $('#zoom-in').addEventListener('click', () => setGraphZoom(graphZoom + .1)); $('#zoom-out').addEventListener('click', () => setGraphZoom(graphZoom - .1));
  $('#fit-graph').addEventListener('click', fitGraph); $('#component-form').addEventListener('submit', applyRule); $('#remove-node').addEventListener('click', removeNode);
  $('#reset-graph').addEventListener('click', resetGraphViewport);
  $('#component-parameters').addEventListener('click', (event) => {
    const button = event.target.closest('[data-disconnect]'); if (!button) return;
    graphEdges = graphEdges.filter((edge) => edge.join(':') !== button.dataset.disconnect); inspectRule(state.selectedNode);
  });
}

function showDialog(name) {
  $('#dialog-content').innerHTML = dialogContent(name);
  $('#studio-dialog').showModal();
  if (name === 'layout') installLayoutControls();
}
function closeDialog() { $('#studio-dialog').close(); }
function dialogContent(name) {
  const views = {new: newDialog, presets: presetsDialog, data: dataDialog, revisions: revisionsDialog, evidence: evidenceDialog, backtest: backtestDialog, layout: layoutDialog, rules: rulesDialog, about: aboutDialog};
  return (views[name] || aboutDialog)();
}
function newDialog() {
  return `<h2 id="dialog-title">Start a new strategy</h2><p>Begin with your own idea, or explore a preset outline.</p><div class="choice-grid"><button class="choice-card" data-action="fresh">${icon('plus')}<strong>Start fresh</strong><small>An empty canvas.<br>Build your first condition.</small></button><button class="choice-card" data-action="presets">${icon('grid')}<strong>Use a preset</strong><small>A starting idea.<br>Make the rules your own.</small></button></div><p class="dialog-note">This preview keeps draft changes in memory only.</p>`;
}
function presetsDialog() {
  return `<h2 id="dialog-title">Presets</h2><p>Explore readable rule outlines before opening a study. These are design examples, not verified executable presets.</p><button class="preset-row" data-action="preset" data-name="EMA trend study"><strong>EMA trend study</strong><small>A rising average with a momentum condition. Inspired by the Trend Impulse research direction.</small></button><button class="preset-row" data-action="preset" data-name="Breakout study"><strong>Breakout study</strong><small>Explore a breakout condition with the same rule workspace. No performance claim.</small></button>`;
}
function rulesDialog() {
  return `<h2 id="dialog-title">Components</h2><div class="palette-list">${Object.entries(componentTypes).map(([key, component]) => `<button class="preset-row" data-action="rule" data-rule-name="${key}"><strong>${component.name}</strong><small>${component.detail}</small></button>`).join('')}</div>`;
}
function addCondition(key) {
  if (!componentTypes[key]) return;
  const node = makeNode(key, 60 + graphNodes.length * 35 % 650, 80 + graphNodes.length * 30 % 240);
  graphNodes.push(node); state.fresh = false; renderGraph(); closeDialog(); inspectRule(node.id);
}
function dataDialog() {
  return `<h2 id="dialog-title">NIFTY 50 price history</h2><p>Real recorded prices, with their limits kept visible.</p><dl class="fact-list"><div><dt>Source</dt><dd>NSE Indices historical export</dd></div><div><dt>Date range</dt><dd>05 Sep 2025 — 04 Sep 2026</dd></div><div><dt>Recorded rows</dt><dd>248 · daily OHLC</dd></div><div><dt>Volume</dt><dd>Not supplied</dd></div><div><dt>Historical availability</dt><dd>Not supplied</dd></div><div><dt>Research role</dt><dd>Benchmark input only</dd></div></dl><div class="notice">Calendar coverage is not asserted. The chart joins recorded rows without filling missing dates. Use a supported equity dataset as the primary input for a real backtest.</div><p class="dialog-note">Local copy for personal research. This preview makes no live market or broker request.</p>`;
}
function revisionsDialog() {
  return `<h2 id="dialog-title">Revisions</h2><p>Example revision history. These entries are not saved records.</p><div class="timeline-row"><strong>Revision 03 · Current example</strong><p>Added a momentum condition alongside the EMA trend rule.</p></div><div class="timeline-row"><strong>Revision 02 · Example baseline</strong><p>Kept the trend rule on completed daily observations.</p></div><div class="notice">No comparison result is available. A real comparison must use attributable runs for both revisions.</div>`;
}
function evidenceDialog() {
  return `<h2 id="dialog-title">Evidence</h2><p>No research evidence has been saved in this preview.</p><dl class="fact-list"><div><dt>Strategy</dt><dd>Example draft</dd></div><div><dt>Dataset</dt><dd>Local NIFTY history</dd></div><div><dt>Run</dt><dd>${state.preview ? 'Example layout only' : 'Not run'}</dd></div><div><dt>Alerts</dt><dd>Not connected</dd></div></dl><div class="notice">In the product, this view would identify the exact revision, data, assumptions and run behind a result.</div>`;
}
function backtestDialog() {
  return `<h2 id="dialog-title">Backtest</h2><p>The research engine is not connected to this design experiment.</p><div class="notice">NIFTY 50 is a benchmark input. A real run needs an eligible primary dataset and a complete strategy. This button only previews the results workspace.</div><dl class="fact-list"><div><dt>Price chart</dt><dd>Real historical OHLC</dd></div><div><dt>Results, trades and alerts</dt><dd>No calculated result</dd></div></dl><div class="dialog-actions"><button class="quiet" data-action="close">Return to study</button><button class="primary" data-action="preview">Preview example run ${icon('arrow')}</button></div>`;
}
function layoutDialog() {
  const [leftMin, leftMax] = bounds('left'), [topMin, topMax] = bounds('top');
  return `<h2 id="dialog-title">Layout</h2><p>Drag a divider, use its arrow keys, or adjust the sliders here. Only pane dimensions are remembered.</p><label class="dialog-field">Watchlist width <output id="left-output">${Math.round(layout.left)} px</output><input type="range" id="layout-left" min="${leftMin}" max="${leftMax}" value="${layout.left}" step="8"></label><label class="dialog-field">Upper pane height <output id="top-output">${Math.round(layout.top)} px</output><input type="range" id="layout-top" min="${topMin}" max="${topMax}" value="${layout.top}" step="8"></label><p class="dialog-note">Divider keys: arrows move 8 px; Shift + arrows move 32 px. Home and End select the bounds. Escape restores an expanded pane.</p><button class="quiet" data-action="reset">Reset layout</button>`;
}
function aboutDialog() { return `<h2 id="dialog-title">About this workspace</h2><p>This is a local desktop prototype. Only the 248 NIFTY price rows are recorded data. There is no account, research engine, saved strategy, trading signal, order connection or performance result.</p><p>The graph is editable presentation state, inspired by the existing Strategy OS node builder. Moving, connecting and editing components does not run or serialize another strategy engine. Changes remain in memory; only pane dimensions are stored.</p><p>Shift+A opens components; Shift+C toggles context; Shift+T toggles toolbars. These shortcuts do not run in text fields. Context and Tools controls remain in the top bar.</p><p>Chart interactions use TradingView Lightweight Charts™ 4.2.3, not Advanced Charts. Pan, wheel zoom, drag either axis to scale, double-click the price axis to reset, and use the crosshair to inspect candles. Drawing tools are not included.</p><p>TradingView Lightweight Charts™<br>Copyright (с) 2024 TradingView, Inc. <a href="https://www.tradingview.com/" target="_blank" rel="noopener">TradingView</a></p>`; }
function installLayoutControls() {
  for (const axis of ['left', 'top']) $(`#layout-${axis}`).addEventListener('input', (event) => {
    restorePanes(); layout[axis] = Number(event.target.value); applyLayout(true); $(`#${axis}-output`).textContent = `${Math.round(layout[axis])} px`;
  });
}
function startFresh() {
  $('#dialog-content').innerHTML = `<h2 id="dialog-title">New strategy</h2><form id="fresh-form"><label class="dialog-field">Strategy name<input id="new-name" required maxlength="60" placeholder="For example, Daily trend study" autocomplete="off"></label><div class="dialog-actions"><button type="button" class="quiet" data-action="new">Back</button><button class="primary" type="submit">Create draft</button></div></form>`;
  $('#new-name').focus(); $('#new-name').addEventListener('input', () => $('#new-name').setCustomValidity('')); $('#fresh-form').addEventListener('submit', (event) => { event.preventDefault(); createFresh($('#new-name').value.trim()); });
}
function createFresh(name) {
  if (!name) { $('#new-name').setCustomValidity('Enter a strategy name.'); $('#new-name').reportValidity(); return; }
  $('#inspector').hidden = true; state.selectedNode = null; state.selectedRule = null; $('#selected-guide').hidden = true;
  $('#strategy-name').textContent = name; state.fresh = true; pendingConnection = null; graphNodes = []; graphEdges = []; renderGraph(); closeDialog();
}
function loadPreset(name) {
  $('#inspector').hidden = true; state.selectedNode = null; state.selectedRule = null; $('#selected-guide').hidden = true;
  $('#strategy-name').textContent = name; resetGraph(name === 'Breakout study'); closeDialog(); fitGraph();
}
function previewRun() {
  state.preview = true; closeDialog(); $('#run-count').textContent = '1';
  $('#runs-view').innerHTML = `<button class="run-card" id="open-example-run"><strong>Review layout preview</strong><small>No trades or returns were computed.</small></button>`;
  $('#open-example-run').addEventListener('click', () => setChartTab('results'));
  $('#results-view').innerHTML = `<div class="result-preview"><h2>Results</h2><p>No calculation was run. These placeholders show where an attributable result would be reviewed.</p><div class="result-metrics"><div><span>Net return</span><strong>—</strong><span>Not calculated</span></div><div><span>Maximum drawdown</span><strong>—</strong><span>Not calculated</span></div><div><span>Completed trades</span><strong>—</strong><span>Not calculated</span></div></div><div class="review-checks"><button data-review="Assumptions">Assumptions ↗</button><button data-review="Robustness">Challenge the result ↗</button><button data-review="Evidence">Evidence ↗</button></div></div>`;
  $$('[data-review]').forEach((button) => button.addEventListener('click', () => showDialog('evidence')));
  setChartTab('results'); setWatchTab('runs'); announce('Example review opened. No backtest was calculated.');
}
function dialogAction(event) {
  const button = event.target.closest('[data-action]'); if (!button) return;
  const actions = {close: closeDialog, fresh: startFresh, preview: previewRun, reset: () => { resetLayout(); closeDialog(); }, preset: () => loadPreset(button.dataset.name), rule: () => addCondition(button.dataset.ruleName), presets: () => { $('#dialog-content').innerHTML = presetsDialog(); }, new: () => { $('#dialog-content').innerHTML = newDialog(); }};
  actions[button.dataset.action]?.();
}
function toggleChrome(name) {
  const hidden = document.body.classList.toggle(`${name}-hidden`);
  $(`#toggle-${name}`).setAttribute('aria-pressed', String(!hidden));
  applyLayout();
}
function installEvents() {
  $$('[data-dialog]').forEach((button) => button.addEventListener('click', () => showDialog(button.dataset.dialog)));
  $$('[data-expand]').forEach((button) => { button.type = 'button'; button.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); expandPane(event.currentTarget.dataset.expand); }); });
  $$('[data-symbol]').forEach((button) => button.addEventListener('click', () => selectInstrument(button.dataset.symbol)));
  $$('[data-chart-tab]').forEach((button) => button.addEventListener('click', () => setChartTab(button.dataset.chartTab)));
  $$('[data-watch]').forEach((button) => button.addEventListener('click', () => setWatchTab(button.dataset.watch)));
  $$('[data-range]').forEach((button) => button.addEventListener('click', () => { state.range = Number(button.dataset.range); lastRange = null; $$('[data-range]').forEach((item) => { const active = item === button; item.classList.toggle('selected', active); item.setAttribute('aria-pressed', active); }); renderChart(); }));
  $('#chart-style').addEventListener('click', () => { state.line = !state.line; $('#chart-style').textContent = state.line ? 'Line' : 'Candles'; $('#chart-style').setAttribute('aria-pressed', state.line); renderChart(); });
  $('#close-dialog').addEventListener('click', closeDialog); $('#dialog-content').addEventListener('click', dialogAction);
  $('#close-inspector').addEventListener('click', closeInspector);
  $('#return-nifty').addEventListener('click', () => selectInstrument('NIFTY 50'));
  $('#home').addEventListener('click', () => { restorePanes(); setChartTab('price'); setWatchTab('watchlist'); });
  $('#add-rule').addEventListener('click', () => showDialog('rules'));
  $('#fresh-add').addEventListener('click', () => showDialog('rules'));
  $('#brand-home').addEventListener('click', () => { restorePanes(); setChartTab('price'); });
  $('#restore-layout').addEventListener('click', restorePanes);
  $('#toggle-context').addEventListener('click', () => toggleChrome('context'));
  $('#toggle-tools').addEventListener('click', () => toggleChrome('tools'));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !$('#studio-dialog').open) { restorePanes(); if (!$('#inspector').hidden) closeInspector(); pendingConnection = null; }
    if (event.target.closest('input,textarea,select,[contenteditable=true]') || event.ctrlKey || event.metaKey || event.altKey || !event.shiftKey || event.repeat || $('#studio-dialog').open) return;
    const key = event.key.toLowerCase();
    if (key === 'a') { event.preventDefault(); showDialog('rules'); }
    if (key === 'c' || key === 't') { event.preventDefault(); toggleChrome(key === 'c' ? 'context' : 'tools'); }
  });
}
installEvents(); installDivider('#vertical-divider', 'left'); installDivider('#horizontal-divider', 'top');
new ResizeObserver(() => applyLayout()).observe(workspace);
installGraphEvents(); resetGraph();
applyLayout(); renderChart(); fitGraph();
const last = rows.at(-1), previous = rows.at(-2), change = last[4] - previous[4];
$('#last-close').textContent = number(last[4]); $('#last-change').textContent = `${change >= 0 ? '+' : ''}${number(change)} (${change >= 0 ? '+' : ''}${(change / previous[4] * 100).toFixed(2)}%)`;
