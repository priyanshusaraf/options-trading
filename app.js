"use strict";

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v))
  ? "—" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });

// ---- IST time formatting for the charts ----------------------------------
function istLabel(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("en-IN", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata",
  });
}

// ---- chart setup ----------------------------------------------------------
const chartTheme = {
  layout: { background: { color: "transparent" }, textColor: "#8B98A5", fontFamily: "JetBrains Mono" },
  grid: { vertLines: { color: "#1B222B" }, horzLines: { color: "#1B222B" } },
  rightPriceScale: { borderColor: "#232A33" },
  timeScale: { borderColor: "#232A33", timeVisible: true, secondsVisible: false,
               tickMarkFormatter: (t) => istLabel(t) },
  crosshair: { vertLine: { color: "#4C8DFF", width: 1 }, horzLine: { color: "#4C8DFF", width: 1 } },
  localization: { timeFormatter: (t) => istLabel(t) },
};

const priceChart = LightweightCharts.createChart($("price-chart"), chartTheme);
const candleSeries = priceChart.addCandlestickSeries({
  upColor: "#2EBD85", downColor: "#F6465D", borderVisible: false,
  wickUpColor: "#2EBD85", wickDownColor: "#F6465D",
});
const emaSeries = priceChart.addLineSeries({ color: "#F0B90B", lineWidth: 2, priceLineVisible: false });

const zChart = LightweightCharts.createChart($("z-chart"), chartTheme);
const zSeries = zChart.addLineSeries({ color: "#4C8DFF", lineWidth: 2, priceLineVisible: false });
let zLines = [];

function syncTimeScales() {
  priceChart.timeScale().subscribeVisibleLogicalRangeChange((r) => {
    if (r) zChart.timeScale().setVisibleLogicalRange(r);
  });
  zChart.timeScale().subscribeVisibleLogicalRangeChange((r) => {
    if (r) priceChart.timeScale().setVisibleLogicalRange(r);
  });
}
syncTimeScales();

new ResizeObserver(() => {
  priceChart.applyOptions({}); zChart.applyOptions({});
}).observe(document.body);

// ---- state ----------------------------------------------------------------
let state = { underlying: "NIFTY 50", interval: "5minute", lastLtp: null, connected: false };
let ltpTimer = null, candleTimer = null;

function banner(msg) {
  const b = $("banner");
  if (!msg) { b.hidden = true; return; }
  b.textContent = msg; b.hidden = false;
}

// ---- connection -----------------------------------------------------------
async function checkStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    state.connected = s.authenticated;
    const btn = $("connect");
    if (!s.has_credentials) {
      btn.textContent = "Add API keys"; btn.className = "conn conn--off";
      banner("Set KITE_API_KEY and KITE_API_SECRET (env vars or config.py), then restart the server.");
      return;
    }
    if (s.authenticated) {
      btn.textContent = "● Connected"; btn.className = "conn conn--on";
      banner(null); startPolling();
    } else {
      btn.textContent = "Connect to Kite"; btn.className = "conn conn--off";
      btn.onclick = () => window.open(s.login_url, "_blank");
      banner("Click Connect to Kite, log in, and you'll be redirected back here.");
    }
  } catch (e) {
    $("connect").textContent = "Server offline"; $("connect").className = "conn conn--off";
  }
}

// ---- data refresh ---------------------------------------------------------
async function refreshLtp() {
  if (!state.connected) return;
  try {
    const r = await fetch(`/api/ltp?underlying=${encodeURIComponent(state.underlying)}`);
    if (!r.ok) return;
    const d = await r.json();
    const el = $("ltp");
    if (d.last_price != null) {
      if (state.lastLtp != null) el.className = "ltp " + (d.last_price >= state.lastLtp ? "up" : "down");
      el.textContent = fmt(d.last_price, 2);
      state.lastLtp = d.last_price;
    }
  } catch (e) { /* transient */ }
}

async function refreshCandles() {
  if (!state.connected) return;
  try {
    const r = await fetch(`/api/candles?underlying=${encodeURIComponent(state.underlying)}&interval=${state.interval}`);
    const d = await r.json();
    if (!r.ok) { banner(d.error || "Could not load candles."); return; }
    banner(null);
    candleSeries.setData(d.candles);
    emaSeries.setData(d.ema);
    candleSeries.setMarkers(d.markers || []);
    zSeries.setData(d.zscore);

    // refresh z-score threshold lines (±entry, 0)
    zLines.forEach((l) => zSeries.removePriceLine(l));
    zLines = [];
    const ez = d.entry_z || 1;
    [[ez, "#2EBD85"], [-ez, "#F6465D"], [0, "#5A6672"]].forEach(([v, c]) => {
      zLines.push(zSeries.createPriceLine({
        price: v, color: c, lineStyle: LightweightCharts.LineStyle.Dashed,
        lineWidth: 1, axisLabelVisible: true,
      }));
    });

    updatePanel(d.latest, ez);
  } catch (e) { banner("Lost connection to the server."); }
}

// ---- signal panel + displacement meter ------------------------------------
function updatePanel(L, entryZ) {
  if (!L) return;
  const card = $("signal-card"), state_el = $("signal-state"), trend_el = $("signal-trend");
  const map = {
    LONG_ENTRY: ["LONG ENTRY", "is-long"], SHORT_ENTRY: ["SHORT ENTRY", "is-short"],
    NONE: [L.trend === "bull" ? "WATCHING ▲" : L.trend === "bear" ? "WATCHING ▼" : "FLAT", "is-flat"],
  };
  const [label, cls] = map[L.signal] || ["FLAT", "is-flat"];
  card.className = "panel signal " + cls;
  state_el.textContent = label;
  trend_el.textContent = `trend ${L.trend} · slope ${fmt(L.slope, 2)}`;

  // values
  $("v-close").textContent = fmt(L.close);
  $("v-ema").textContent = fmt(L.ema);
  $("v-ema5").textContent = fmt(L.ema_5_ago);
  const slope = $("v-slope"); slope.textContent = fmt(L.slope, 2);
  slope.className = L.slope > 0 ? "pos" : L.slope < 0 ? "neg" : "";
  const z = $("v-z"); z.textContent = fmt(L.z, 3);
  z.className = L.z > 0 ? "pos" : L.z < 0 ? "neg" : "";
  $("v-zprev").textContent = fmt(L.z_prev, 3);
  $("v-std").textContent = fmt(L.std, 3);
  $("v-exit").textContent = `${L.long_exit ? "Y" : "·"} / ${L.short_exit ? "Y" : "·"}`;

  // displacement meter: map z in [-3,+3] to 0..100%
  const clamped = Math.max(-3, Math.min(3, L.z));
  const pct = ((clamped + 3) / 6) * 100;
  const marker = $("track-marker"), fill = $("track-fill"), read = $("meter-read");
  marker.style.left = pct + "%";
  const col = L.z >= entryZ ? "#2EBD85" : L.z <= -entryZ ? "#F6465D" : "#4C8DFF";
  marker.style.background = col;
  marker.style.boxShadow = `0 0 0 4px ${col}30`;
  // fill from center (50%) to marker
  if (pct >= 50) { fill.style.left = "50%"; fill.style.width = (pct - 50) + "%"; }
  else { fill.style.left = pct + "%"; fill.style.width = (50 - pct) + "%"; }
  fill.style.background = col + "33";
  read.textContent = `z = ${fmt(L.z, 3)}   (entry at ±${entryZ})`;
}

// ---- polling control ------------------------------------------------------
function startPolling() {
  clearInterval(ltpTimer); clearInterval(candleTimer);
  refreshLtp(); refreshCandles();
  ltpTimer = setInterval(refreshLtp, 3000);      // live price every 3s
  candleTimer = setInterval(refreshCandles, 20000); // candles/signals every 20s
}

// ---- init -----------------------------------------------------------------
async function init() {
  const meta = await (await fetch("/api/meta")).json();
  const us = $("underlying"), iv = $("interval");
  meta.underlyings.forEach((u) => us.add(new Option(u, u)));
  meta.intervals.forEach((i) => iv.add(new Option(i, i)));
  us.value = state.underlying = meta.defaults ? "NIFTY 50" : meta.underlyings[0];
  iv.value = state.interval = (meta.defaults && meta.defaults.interval) || "5minute";

  us.onchange = () => { state.underlying = us.value; state.lastLtp = null; refreshLtp(); refreshCandles(); };
  iv.onchange = () => { state.interval = iv.value; refreshCandles(); };

  await checkStatus();
  setInterval(checkStatus, 15000); // re-check auth (token can expire)
}
init();
