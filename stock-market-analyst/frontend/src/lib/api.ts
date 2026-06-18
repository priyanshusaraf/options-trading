import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// ── Types ──────────────────────────────────────────────────────────────────────

export interface WatchlistItem {
  id: number;
  symbol: string;
  exchange: string;
  sector?: string;
  industry?: string;
  notes?: string;
  added_at: string;
  is_active: boolean;
}

export interface QuantResult {
  symbol: string;
  observations: number;
  returns: { total: number; annualized: number };
  risk: {
    annualized_vol: number;
    rolling_vol_30d: number;
    rolling_vol_90d: number;
    beta: number;
    alpha_annualized: number;
    r_squared: number;
  };
  ratios: { sharpe: number; sortino: number; calmar: number };
  var: { hist_95: number; hist_99: number; param_95: number; cvar_95: number };
  drawdown: { max: number; current: number; duration_days: number };
  factors: { momentum: number; volatility: number; value: number; size: number };
  composite_score: number;
  distribution: { skewness: number; kurtosis: number };
}

export interface TechnicalResult {
  symbol: string;
  signal: string;
  confidence: number;
  probabilities: {
    bullish: number;
    bearish: number;
    breakout: number;
    reversal: number;
  };
  indicators: {
    rsi_14: number;
    macd: { line: number; signal: number; histogram: number; crossover: string };
    bollinger: { upper: number; middle: number; lower: number; pct_b: number; bandwidth: number };
    moving_averages: { ma_20: number; ma_50: number; ma_200: number; cross: string };
    atr_14: number;
    adx_14: number;
    trend_strength: number;
  };
}

export interface RegimeResult {
  regime: string;
  confidence: number;
  vol_regime: string;
  trend_strength: number;
  is_trending: boolean;
  is_mean_reverting: boolean;
  realized_vol_30d: number;
  realized_vol_90d: number;
  description: string;
  signal_adjustments: {
    momentum_weight: number;
    mean_reversion_weight: number;
    vol_risk_discount: number;
  };
}

export interface Opportunity {
  symbol: string;
  action: string;
  score: number;
  confidence: number;
  suggested_weight_pct: number;
  quant_score: number;
  technical_score: number;
  reasons: string[];
  warnings: string[];
  metrics: Record<string, unknown>;
}

export interface OHLCVPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ── API Functions ──────────────────────────────────────────────────────────────

export interface StockSearchResult {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  index?: string;
  exchange?: string;
}

export const watchlistApi = {
  list: () => api.get<WatchlistItem[]>("/watchlist/").then((r) => r.data),
  add: (data: { symbol: string; exchange?: string; sector?: string; industry?: string; notes?: string }) =>
    api.post<WatchlistItem>("/watchlist/", data).then((r) => r.data),
  remove: (symbol: string) => api.delete(`/watchlist/${symbol}`),
  update: (symbol: string, data: Partial<WatchlistItem>) =>
    api.patch<WatchlistItem>(`/watchlist/${symbol}`, data).then((r) => r.data),
  search: (q: string, limit = 12) =>
    api.get<{ query: string; total_in_db: number; results: StockSearchResult[] }>(
      "/watchlist/search", { params: { q, limit } }
    ).then((r) => r.data.results),
  searchLive: (q: string) =>
    api.get<StockSearchResult[]>("/watchlist/search/live", { params: { q } }).then((r) => r.data),
};

export const analysisApi = {
  quant: (symbol: string, days = 756) =>
    api.get<QuantResult>(`/analysis/quant/${symbol}`, { params: { days } }).then((r) => r.data),
  technical: (symbol: string, days = 365) =>
    api.get<TechnicalResult>(`/analysis/technical/${symbol}`, { params: { days } }).then((r) => r.data),
  regime: (days = 365) =>
    api.get<RegimeResult>("/analysis/regime", { params: { days } }).then((r) => r.data),
  opportunities: (days = 756, limit = 20) =>
    api
      .get<{ regime: string; opportunities: Opportunity[] }>("/analysis/opportunities", {
        params: { days, limit },
      })
      .then((r) => r.data),
  correlation: (symbols: string[], days = 252) =>
    api
      .get<{ symbols: string[]; matrix: Record<string, Record<string, number>> }>("/analysis/correlation", {
        params: { symbols: symbols.join(","), days },
      })
      .then((r) => r.data),
  correlationMatrix: (days = 90) =>
    api
      .get<{ symbols: string[]; matrix: Record<string, Record<string, number>> }>("/analysis/correlation", {
        params: { days },
      })
      .then((r) => r.data),
  rollingCorrelation: (symbol1: string, symbol2: string, window = 30) =>
    api
      .get(`/analysis/rolling-correlation`, {
        params: { symbol1, symbol2, window },
      })
      .then((r) => r.data),
};

export const dataApi = {
  ohlcv: (symbol: string, days = 365) =>
    api
      .get<{ data: OHLCVPoint[] }>(`/data/ohlcv/${symbol}`, { params: { days } })
      .then((r) => r.data),
  fundamentals: (symbol: string) =>
    api.get(`/data/fundamentals/${symbol}`).then((r) => r.data),
  macro: () => api.get("/data/macro").then((r) => r.data),
  health: () => api.get("/health", { baseURL: "http://localhost:8000" }).then((r) => r.data),
};

export const intelligenceApi = {
  news: (symbol: string, days = 7) =>
    api.get(`/intelligence/news/${symbol}`, { params: { days } }).then((r) => r.data),
  marketNews: (days = 3) =>
    api.get("/intelligence/news/market/overview", { params: { days } }).then((r) => r.data),
  calendar: (days_ahead = 30, impact_level?: string) =>
    api.get("/intelligence/calendar", { params: { days_ahead, impact_level } }).then((r) => r.data),
  graph: () => api.get("/intelligence/graph").then((r) => r.data),
  disruption: (node: string, magnitude = 0.5) =>
    api.get(`/intelligence/graph/disruption/${node}`, { params: { magnitude } }).then((r) => r.data),
  supplyRisk: (symbol: string) =>
    api.get(`/intelligence/graph/risk/${symbol}`).then((r) => r.data),
};

export const portfolioApi = {
  get: () => api.get("/portfolio/").then((r) => r.data),
  addHolding: (data: { symbol: string; quantity: number; avg_cost: number; exchange?: string }) =>
    api.post("/portfolio/holdings", data).then((r) => r.data),
  removeHolding: (symbol: string) => api.delete(`/portfolio/holdings/${symbol}`),
  listHoldings: () => api.get("/portfolio/holdings").then((r) => r.data),
  kiteStatus: () => api.get("/portfolio/kite/status").then((r) => r.data),
};

export const commodityApi = {
  list: () => api.get("/commodities/").then((r) => r.data),
  linkage: (symbol: string, sector?: string) =>
    api.get(`/commodities/linkage/${symbol}`, { params: { sector } }).then((r) => r.data),
  overview: (days = 30) =>
    api.get("/commodities/market-overview", { params: { days } }).then((r) => r.data),
};

export const optionsApi = {
  chain: (symbol: string, spot?: number) =>
    api.get(`/options/chain/${symbol}`, { params: { spot } }).then((r) => r.data),
};

export interface AlertItem {
  id: number;
  symbol: string;
  alert_type: string;
  threshold: number;
  condition: string;
  triggered: boolean;
  triggered_at: string | null;
  created_at: string;
  notes: string;
}

export const alertsApi = {
  list: (symbol?: string, triggered?: boolean) =>
    api.get("/alerts/", { params: { symbol, triggered } }).then((r) => r.data as AlertItem[]),
  create: (data: { symbol: string; alert_type: string; threshold: number; condition?: string; notes?: string }) =>
    api.post("/alerts/", data).then((r) => r.data as AlertItem),
  delete: (id: number) => api.delete(`/alerts/${id}`),
  reset: (id: number) => api.post(`/alerts/${id}/reset`).then((r) => r.data as AlertItem),
  evaluateAll: () => api.post("/alerts/evaluate/all").then((r) => r.data),
  recent: (limit = 20) => api.get("/alerts/triggered/recent", { params: { limit } }).then((r) => r.data as AlertItem[]),
};

export const macroApi = {
  series: (series_ids: string[], start?: string, end?: string) =>
    api.get("/data/macro", { params: { series_ids: series_ids.join(","), start, end } }).then((r) => r.data),
  yieldCurve: () =>
    api.get("/data/macro", { params: { series_ids: "DGS3MO,DGS2,DGS5,DGS10,DGS30" } }).then((r) => r.data),
};

export const positionSizerApi = {
  compute: (
    symbols: string[],
    options?: { kelly_fraction?: number; max_position_pct?: number; method?: string }
  ) =>
    api.post("/analysis/position-sizing", { symbols, ...options }).then((r) => r.data),
};
