// Interaction checks only. Real chart canvas and pointer hit testing need browser QA.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('/Users/priyanshusaraf/dev/strategy-os-frontend/node_modules/jsdom');
const dom = new JSDOM(fs.readFileSync(__dirname + '/index.html', 'utf8'), {runScripts: 'outside-only', url: 'http://localhost/'});
const w = dom.window, d = w.document, series = [], calls = {};
Object.defineProperty(w.HTMLElement.prototype, 'clientWidth', {get() { return this.id === 'workspace' ? 1300 : this.id === 'graph-viewport' ? 1260 : 900; }});
Object.defineProperty(w.HTMLElement.prototype, 'clientHeight', {get() { return this.id === 'workspace' ? 780 : 330; }});
w.HTMLElement.prototype.setPointerCapture = function () {};
w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
w.HTMLDialogElement.prototype.close = function () { this.open = false; };
w.ResizeObserver = class { constructor(callback) { calls.resizeObserver = callback; } observe() {} disconnect() {} };
w.LightweightCharts = {CrosshairMode: {Normal: 0}, createChart(host, options) {
  calls.options = options;
  const add = () => { const value = {setData(data) { this.data = data; }, applyOptions(options) { this.options = options; }}; series.push(value); return value; };
  return {addCandlestickSeries: add, addLineSeries: add, subscribeCrosshairMove(fn) { calls.hover = fn; }, resize() { calls.range = null; }, timeScale() { return {getVisibleLogicalRange() { return calls.range; }, setVisibleLogicalRange(range) { calls.range = range; }, subscribeVisibleTimeRangeChange(fn) { calls.timeRange = fn; }}; }};
}};
w.eval(fs.readFileSync(__dirname + '/history.js', 'utf8'));
w.eval(fs.readFileSync(__dirname + '/studio.js', 'utf8'));
const click = (selector) => d.querySelector(selector).dispatchEvent(new w.MouseEvent('click', {bubbles: true, cancelable: true}));
const key = (target, value, shift = false) => target.dispatchEvent(new w.KeyboardEvent('keydown', {key: value, shiftKey: shift, bubbles: true, cancelable: true}));
const pointer = (target, type, x, y, button = 0) => target.dispatchEvent(new w.MouseEvent(type, {clientX: x, clientY: y, button, bubbles: true, cancelable: true}));
assert.equal(w.NIFTY_HISTORY.length, 248); assert.equal(series[0].data.length, 248);
assert.equal(calls.options.handleScale.axisPressedMouseMove.price, true);
const originalRange = calls.range; calls.resizeObserver(); assert.equal(calls.range, originalRange);
assert.equal(calls.options.handleScroll.pressedMouseMove, true);
calls.hover({time: w.NIFTY_HISTORY[0][0]}); assert(d.querySelector('#ohlc').textContent.includes('05 Sept 2025') || d.querySelector('#ohlc').textContent.includes('05 Sep 2025'));
click('[data-range="21"]'); assert.equal(calls.range.from, 227);
calls.timeRange({from: '2025-09-05', to: '2025-10-01'}); assert(d.querySelector('#date-range').textContent.includes('01 Oct 2025'));
click('[data-symbol="RELIANCE"]'); assert.equal(d.querySelector('#chart-empty').hidden, false); assert.equal(d.querySelector('#price-chart').style.visibility, 'hidden');
click('#return-nifty'); assert.equal(d.querySelector('#chart-empty').hidden, true);
for (const pane of ['watch', 'chart', 'builder']) {
  click(`[data-expand="${pane}"] svg use`); assert.equal(d.querySelector('#workspace').dataset.expanded, pane);
  assert.equal(d.querySelector('#restore-layout').hidden, false); click('#restore-layout'); assert.equal(d.querySelector('#workspace').dataset.expanded, undefined);
}
assert.equal(d.querySelector('.brand').tagName, 'BUTTON');
const divider = d.querySelector('#vertical-divider'); key(divider, 'End'); assert.equal(divider.getAttribute('aria-valuenow'), '560');
pointer(divider, 'pointerdown', 500, 0); pointer(divider, 'pointermove', -500, 0); pointer(divider, 'pointerup', -500, 0); assert.equal(divider.getAttribute('aria-valuenow'), '240');
assert.deepEqual(Object.keys(JSON.parse(w.localStorage.getItem('strategy-os.desktop-studio.layout.v1'))), ['left', 'top']);
click('#toggle-tools'); click('#toggle-context'); assert(d.body.classList.contains('tools-hidden')); assert(d.body.classList.contains('context-hidden'));
key(d.body, 'A', true); assert(d.querySelector('#studio-dialog').open); assert.equal(d.querySelector('#dialog-title').textContent, 'Components'); click('#close-dialog');
assert.equal(d.querySelectorAll('.graph-node').length, 6); assert.equal(d.querySelectorAll('#graph-edges path').length, 6);
assert.deepEqual([...d.querySelectorAll('.graph-node')].map((n) => n.dataset.nodeFamily), ['TYPE_4', 'TYPE_2', 'TYPE_2', 'TYPE_2', 'TYPE_5', 'TYPE_5']);
assert.equal(d.querySelector('.node-family-label').textContent, 'Type 4');
const viewport = d.querySelector('#graph-viewport'), world = d.querySelector('#rule-flow');
const positions = () => [...d.querySelectorAll('.graph-node')].map((n) => [n.style.left, n.style.top]);
const beforePan = positions(), firstView = world.style.transform;
pointer(world, 'pointerdown', 300, 180); pointer(viewport, 'pointermove', 420, 220); pointer(viewport, 'pointerup', 420, 220);
assert.notEqual(world.style.transform, firstView); assert.deepEqual(positions(), beforePan);
let panView = world.style.transform;
pointer(d.querySelector('.graph-node'), 'pointerdown', 70, 70, 1); pointer(viewport, 'pointermove', 130, 100, 1); pointer(viewport, 'pointerup', 130, 100, 1);
assert.notEqual(world.style.transform, panView); assert.deepEqual(positions(), beforePan);
panView = world.style.transform; key(viewport, ' ');
pointer(d.querySelector('.graph-node'), 'pointerdown', 70, 70); pointer(viewport, 'pointermove', 120, 110); pointer(viewport, 'pointerup', 120, 110);
d.dispatchEvent(new w.KeyboardEvent('keyup', {key: ' ', bubbles: true}));
assert.notEqual(world.style.transform, panView); assert.deepEqual(positions(), beforePan);
panView = world.style.transform; key(viewport, 'ArrowRight'); assert.notEqual(world.style.transform, panView); assert.deepEqual(positions(), beforePan);
key(viewport, 'Home'); assert.deepEqual(positions(), beforePan); click('#reset-graph'); assert.equal(world.style.transform, 'translate(0px, 0px) scale(1)');
pointer(viewport, 'pointerdown', 10, 10); pointer(viewport, 'pointercancel', 10, 10); panView = world.style.transform;
pointer(viewport, 'pointermove', 60, 70); assert.equal(world.style.transform, panView);
const portKey = d.querySelector('.graph-node .output');
assert.equal(key(portKey, ' '), true); assert(!viewport.classList.contains('pan-ready'));
assert.equal(key(d.body, ' '), true); assert(!viewport.classList.contains('pan-ready'));
key(portKey, 'Enter'); assert.equal(d.querySelector('#inspector').hidden, true);
const beforePortArrow = positions(); key(portKey, 'ArrowDown'); assert.deepEqual(positions(), beforePortArrow);
let node = d.querySelector('.graph-node');
for (let i = 0; i < 24; i++) key(node, 'ArrowDown', true);
click('#fit-graph');
const viewNumbers = world.style.transform.match(/-?[\d.]+/g).map(Number), [panX, panY, scale] = viewNumbers;
for (const card of d.querySelectorAll('.graph-node')) {
  assert(parseFloat(card.style.left) * scale + panX >= 0);
  assert((parseFloat(card.style.left) + 190) * scale + panX <= viewport.clientWidth);
  assert(parseFloat(card.style.top) * scale + panY >= 0);
  assert((parseFloat(card.style.top) + 86) * scale + panY <= viewport.clientHeight);
}
click('#reset-graph'); node = d.querySelector('.graph-node'); const originalLeft = parseFloat(node.style.left);
pointer(node, 'pointerdown', 50, 50); pointer(node, 'pointermove', 100, 70); pointer(node, 'pointerup', 100, 70); assert(parseFloat(node.style.left) > originalLeft);
click('.graph-node'); click('.graph-node'); assert.equal(d.querySelector('#inspector').hidden, false);
key(d.querySelector('#node-name'), 'A', true); assert.equal(d.querySelector('#studio-dialog').open, false);
d.querySelector('#node-name').value = 'Recorded prices'; d.querySelector('#component-form').dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true})); assert.equal(d.querySelector('.node-title strong').textContent, 'Recorded prices');
click('#close-inspector'); click('.graph-node:first-child .output'); click('.graph-node:last-child .input'); assert.equal(d.querySelectorAll('#graph-edges path').length, 7);
click('.graph-node:last-child'); click('#remove-node'); assert.equal(d.querySelectorAll('.graph-node').length, 5); assert.equal(d.querySelectorAll('#graph-edges path').length, 5);
key(d.body, 'C', true); key(d.body, 'T', true); assert(!d.body.classList.contains('tools-hidden')); assert(!d.body.classList.contains('context-hidden'));
click('[data-dialog="new"]'); click('[data-action="fresh"]'); d.querySelector('#new-name').value = 'Own study'; d.querySelector('#fresh-form').dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true})); assert.equal(d.querySelectorAll('.graph-node').length, 0);
click('#fit-graph'); assert.equal(world.style.transform, 'translate(0px, 0px) scale(1)');
click('#fresh-add'); click('[data-rule-name="trend"]'); assert.equal(d.querySelectorAll('.graph-node').length, 1);
assert(!d.body.textContent.includes('DESIGN PREVIEW')); assert(!d.querySelector('.status-bar'));
console.log('PASS: 248 OHLC rows, chart configuration/crosshair, pane resize/restore, canvas pan without node edits, keyboard pan, node family labels, node drag/edit/connect/remove, fresh/add. Browser canvas/rendering not tested.');
dom.window.close();
if (process.argv.includes('--mutations')) {
  const path = require('node:path'), child = require('node:child_process');
  const source = fs.readFileSync(__dirname + '/studio.js', 'utf8');
  const mutations = [
    ['fit-bottom', 'node.y + 86', '86'],
    ['fit-offset', '(bottom + top) * graphZoom', '(bottom - top) * graphZoom'],
    ['space-button-guard', 'button,a,input,textarea,select,[contenteditable=true]', 'input,textarea,select,[contenteditable=true]'],
    ['space-focus-scope', '!viewport.contains(event.target) || ', ''],
    ['node-descendant-guard', ' || event.target !== element', ''],
    ['pan-write', 'graphPan = {x: drag.left + dx, y: drag.top + dy}', 'graphPan = {x: drag.left, y: drag.top}'],
    ['resize-range', 'if (range) chart.timeScale().setVisibleLogicalRange(range);', ''],
    ['expand-target', 'expandPane(event.currentTarget.dataset.expand)', "expandPane('watch')"],
    ['shortcut-input-guard', "event.target.closest('input,textarea,select,[contenteditable=true]') || ", ''],
    ['connection-write', 'graphEdges.push([pendingConnection, id])', 'void 0'],
    ['crosshair-ohlc', 'if (row) showOhlc(row);', ''],
    ['missing-history', "const empty = state.symbol !== 'NIFTY 50';", 'const empty = false;'],
  ];
  for (const [name, before, after] of mutations) {
    assert.equal(source.split(before).length, 2, `single mutation target: ${name}`);
    const directory = fs.mkdtempSync(path.join(__dirname, '.mutation-'));
    try {
      for (const file of ['index.html', 'history.js', 'check.cjs']) fs.copyFileSync(path.join(__dirname, file), path.join(directory, file));
      fs.writeFileSync(path.join(directory, 'studio.js'), source.replace(before, after));
      const result = child.spawnSync(process.execPath, [path.join(directory, 'check.cjs')], {encoding: 'utf8'});
      assert(result.status !== 0 && result.stderr.includes('AssertionError'), `${name} must be caught by an assertion, not a runtime failure`);
      console.log(`KILLED: ${name}`);
    } finally { fs.rmSync(directory, {recursive: true, force: true}); }
  }
}
