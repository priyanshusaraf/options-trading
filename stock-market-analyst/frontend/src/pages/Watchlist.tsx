import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { watchlistApi, WatchlistItem, StockSearchResult } from "../lib/api";
import {
  Plus, Trash2, Search, Loader2, CheckCircle2,
  Clock, X, ChevronDown, RefreshCw,
} from "lucide-react";
import { cn } from "../lib/utils";

// ── Sector colour map ─────────────────────────────────────────────────────────
const SECTOR_STYLES: Record<string, string> = {
  "Technology":        "bg-blue-500/15 text-blue-300 border-blue-500/20",
  "Financials":        "bg-emerald-500/15 text-emerald-300 border-emerald-500/20",
  "Healthcare":        "bg-rose-500/15 text-rose-300 border-rose-500/20",
  "Energy":            "bg-amber-500/15 text-amber-300 border-amber-500/20",
  "Consumer Staples":  "bg-violet-500/15 text-violet-300 border-violet-500/20",
  "Consumer Discret.": "bg-orange-500/15 text-orange-300 border-orange-500/20",
  "Industrials":       "bg-cyan-500/15 text-cyan-300 border-cyan-500/20",
  "Materials":         "bg-lime-500/15 text-lime-300 border-lime-500/20",
  "Utilities":         "bg-teal-500/15 text-teal-300 border-teal-500/20",
  "Communication":     "bg-purple-500/15 text-purple-300 border-purple-500/20",
  "Real Estate":       "bg-pink-500/15 text-pink-300 border-pink-500/20",
  "Unknown":           "bg-gray-500/15 text-gray-400 border-gray-600/20",
};

function SectorBadge({ sector }: { sector?: string }) {
  if (!sector || sector === "Unknown") return null;
  const cls = SECTOR_STYLES[sector] ?? SECTOR_STYLES["Unknown"];
  return (
    <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full border", cls)}>
      {sector}
    </span>
  );
}

// ── Dropdown result row ───────────────────────────────────────────────────────
function ResultRow({
  stock,
  highlighted,
  onMouseEnter,
  onSelect,
  alreadyAdded,
}: {
  stock: StockSearchResult;
  highlighted: boolean;
  onMouseEnter: () => void;
  onSelect: () => void;
  alreadyAdded: boolean;
}) {
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onSelect(); }}
      onMouseEnter={onMouseEnter}
      className={cn(
        "w-full flex items-center gap-3 px-4 py-2.5 text-left border-b border-gray-800/60 last:border-0 transition-colors",
        highlighted ? "bg-indigo-600/25" : "hover:bg-gray-800/60",
        alreadyAdded && "opacity-60"
      )}
    >
      {/* Symbol */}
      <span className="w-24 shrink-0 font-mono font-bold text-white text-sm truncate">
        {stock.symbol}
      </span>
      {/* Name + industry */}
      <span className="flex-1 min-w-0">
        <span className="block text-sm text-gray-200 truncate">{stock.name}</span>
        {stock.industry && (
          <span className="text-xs text-gray-500">{stock.industry}</span>
        )}
      </span>
      {/* Right side */}
      <span className="shrink-0 flex items-center gap-2">
        {stock.index && (
          <span className="text-xs text-gray-600 hidden sm:block">{stock.index}</span>
        )}
        <SectorBadge sector={stock.sector} />
        {alreadyAdded && (
          <CheckCircle2 size={13} className="text-emerald-400" />
        )}
      </span>
    </button>
  );
}

// ── Search Input + Dropdown ───────────────────────────────────────────────────
function StockSearchDropdown({
  existingSymbols,
  onSelect,
}: {
  existingSymbols: Set<string>;
  onSelect: (s: StockSearchResult) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: results = [], isFetching } = useQuery<StockSearchResult[]>({
    queryKey: ["nse-search", query],
    queryFn: () => watchlistApi.search(query, 15),
    enabled: query.length >= 1,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });

  // Close on outside click
  useEffect(() => {
    const fn = (e: MouseEvent) => {
      if (!listRef.current?.contains(e.target as Node) &&
          !inputRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  useEffect(() => setHighlighted(0), [results]);

  const select = useCallback((stock: StockSearchResult) => {
    onSelect(stock);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  }, [onSelect]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setHighlighted(h => Math.min(h + 1, results.length - 1)); }
    if (e.key === "ArrowUp")   { e.preventDefault(); setHighlighted(h => Math.max(h - 1, 0)); }
    if (e.key === "Enter")     { e.preventDefault(); if (results[highlighted]) select(results[highlighted]); }
    if (e.key === "Escape")    { setOpen(false); inputRef.current?.blur(); }
  };

  const showDropdown = open && query.length >= 1;

  return (
    <div className="relative">
      {/* Input */}
      <div className="relative flex items-center">
        <Search size={15} className="absolute left-3.5 text-gray-500 pointer-events-none" />
        <input
          ref={inputRef}
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => { if (query.length >= 1) setOpen(true); }}
          onKeyDown={onKeyDown}
          placeholder="Type a company name or ticker — e.g. Infosys, HDFC, Tata…"
          autoComplete="off"
          spellCheck={false}
          className="w-full bg-gray-800 border border-gray-700 rounded-xl pl-10 pr-10 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 transition-colors"
        />
        <div className="absolute right-3.5 flex items-center gap-1">
          {isFetching && <Loader2 size={13} className="animate-spin text-gray-500" />}
          {query && !isFetching && (
            <button onClick={() => { setQuery(""); setOpen(false); }} className="text-gray-500 hover:text-white p-0.5">
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div
          ref={listRef}
          className="absolute top-full left-0 right-0 mt-1.5 z-50 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden"
        >
          {results.length === 0 && !isFetching && (
            <div className="px-4 py-4 text-gray-500 text-sm text-center">
              No results for "<span className="text-gray-300">{query}</span>"
              <p className="text-xs mt-1 text-gray-600">Try the full company name or exact NSE symbol</p>
            </div>
          )}
          {results.map((stock, i) => (
            <ResultRow
              key={stock.symbol}
              stock={stock}
              highlighted={i === highlighted}
              onMouseEnter={() => setHighlighted(i)}
              onSelect={() => select(stock)}
              alreadyAdded={existingSymbols.has(stock.symbol)}
            />
          ))}
          <div className="px-4 py-2 bg-gray-950/80 flex items-center justify-between">
            <span className="text-xs text-gray-600">
              {results.length > 0
                ? `${results.length} result${results.length !== 1 ? "s" : ""} · 2,364 NSE equities indexed`
                : "2,364 NSE equities indexed"}
            </span>
            <span className="text-xs text-gray-700">↑↓ navigate · Enter select</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Pending confirm panel ─────────────────────────────────────────────────────
function ConfirmPanel({
  stock,
  alreadyAdded,
  onConfirm,
  onCancel,
  isPending,
  error,
}: {
  stock: StockSearchResult;
  alreadyAdded: boolean;
  onConfirm: (sector?: string) => void;
  onCancel: () => void;
  isPending: boolean;
  error?: string | null;
}) {
  const [sector, setSector] = useState(stock.sector !== "Unknown" ? stock.sector : "");

  return (
    <div className="mt-3 bg-gray-800/50 border border-gray-700 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="font-mono font-bold text-white text-lg">{stock.symbol}</span>
            <span className="text-gray-300 text-sm">{stock.name}</span>
            {alreadyAdded && (
              <span className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-full">
                Already in watchlist
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <SectorBadge sector={stock.sector !== "Unknown" ? stock.sector : undefined} />
            {stock.industry && <span className="text-xs text-gray-500">{stock.industry}</span>}
            {stock.index && <span className="text-xs text-gray-600">{stock.index}</span>}
            {stock.isin && <span className="text-xs text-gray-700 font-mono">{stock.isin}</span>}
          </div>
          {/* Sector override */}
          <div className="mt-3">
            <label className="text-xs text-gray-500 block mb-1">Sector (optional override)</label>
            <input
              value={sector}
              onChange={e => setSector(e.target.value)}
              placeholder={stock.sector !== "Unknown" ? stock.sector : "e.g. Technology"}
              className="w-full sm:w-64 bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
            />
          </div>
          {error && (
            <p className="mt-2 text-sm text-red-400 bg-red-950/30 border border-red-800/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>
        {/* Actions */}
        <div className="flex flex-col gap-2 shrink-0">
          <button
            onClick={() => onConfirm(sector || undefined)}
            disabled={isPending}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
          >
            {isPending
              ? <><Loader2 size={13} className="animate-spin" /> Adding…</>
              : <><CheckCircle2 size={13} /> Add to watchlist</>}
          </button>
          <button
            onClick={onCancel}
            className="text-center text-sm text-gray-500 hover:text-gray-300 py-1 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Watchlist row ─────────────────────────────────────────────────────────────
function WatchlistRow({
  item,
  isNew,
  onRemove,
}: {
  item: WatchlistItem;
  isNew: boolean;
  onRemove: () => void;
}) {
  const sectorDot: Record<string, string> = {
    "Technology":        "bg-blue-400",
    "Financials":        "bg-emerald-400",
    "Healthcare":        "bg-rose-400",
    "Energy":            "bg-amber-400",
    "Consumer Staples":  "bg-violet-400",
    "Consumer Discret.": "bg-orange-400",
    "Industrials":       "bg-cyan-400",
    "Materials":         "bg-lime-400",
    "Utilities":         "bg-teal-400",
    "Communication":     "bg-purple-400",
    "Real Estate":       "bg-pink-400",
  };
  const dot = sectorDot[item.sector || ""] ?? "bg-gray-600";

  return (
    <div className={cn(
      "flex items-center gap-3 px-4 py-3 rounded-xl border transition-all group",
      isNew
        ? "bg-indigo-950/25 border-indigo-600/30"
        : "bg-gray-900 border-gray-800 hover:border-gray-600"
    )}>
      {/* Sector dot */}
      <div className={cn("w-2 h-2 rounded-full shrink-0", dot)} />

      {/* Symbol */}
      <span className="w-28 shrink-0 font-mono font-bold text-white text-sm">{item.symbol}</span>

      {/* Name placeholder / sector */}
      <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
        {item.sector && item.sector !== "Unknown" && (
          <SectorBadge sector={item.sector} />
        )}
        {item.industry && (
          <span className="text-xs text-gray-600 truncate">{item.industry}</span>
        )}
        {item.notes && (
          <span className="text-xs text-gray-700 italic truncate hidden sm:block">{item.notes}</span>
        )}
      </div>

      {/* Right side */}
      <div className="flex items-center gap-3 shrink-0">
        {isNew && (
          <span className="flex items-center gap-1 text-xs text-amber-400/80">
            <Clock size={11} /> fetching…
          </span>
        )}
        <span className="text-xs text-gray-700 hidden sm:block">
          {new Date(item.added_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "2-digit" })}
        </span>
        <button
          onClick={onRemove}
          className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-1 rounded"
          title="Remove"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function Watchlist() {
  const qc = useQueryClient();
  const [pending, setPending] = useState<StockSearchResult | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [recentlyAdded, setRecentlyAdded] = useState<Set<string>>(new Set());

  const { data: items = [], isLoading } = useQuery<WatchlistItem[]>({
    queryKey: ["watchlist"],
    queryFn: watchlistApi.list,
    refetchInterval: 20_000,
  });

  const addMut = useMutation({
    mutationFn: watchlistApi.add,
    onSuccess: (item) => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      setRecentlyAdded(prev => new Set([...prev, item.symbol]));
      setPending(null);
      setAddError(null);
      setTimeout(() => {
        setRecentlyAdded(prev => { const n = new Set(prev); n.delete(item.symbol); return n; });
      }, 45_000);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      setAddError(
        typeof detail === "string"
          ? detail
          : "Could not add symbol — check the ticker is listed on NSE."
      );
    },
  });

  const removeMut = useMutation({
    mutationFn: (symbol: string) => watchlistApi.remove(symbol),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const handleConfirm = (sector?: string) => {
    if (!pending) return;
    addMut.mutate({
      symbol: pending.symbol,
      exchange: "NSE",
      sector: sector || (pending.sector !== "Unknown" ? pending.sector : undefined),
      industry: pending.industry || undefined,
    });
  };

  const existingSymbols = new Set(items.map(i => i.symbol));

  // Group by sector for display
  const grouped: Record<string, WatchlistItem[]> = {};
  for (const item of items) {
    const s = item.sector || "Unknown";
    (grouped[s] ||= []).push(item);
  }
  const sortedSectors = Object.keys(grouped).sort((a, b) =>
    a === "Unknown" ? 1 : b === "Unknown" ? -1 : grouped[b].length - grouped[a].length
  );

  return (
    <div className="space-y-5 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Watchlist</h1>
        <p className="text-gray-500 text-sm mt-0.5">
          Search all 2,364 NSE-listed companies by name or ticker. Historical data fetches automatically.
        </p>
      </div>

      {/* Search card */}
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-5 space-y-3">
        <StockSearchDropdown existingSymbols={existingSymbols} onSelect={s => { setPending(s); setAddError(null); }} />

        {pending && (
          <ConfirmPanel
            stock={pending}
            alreadyAdded={existingSymbols.has(pending.symbol)}
            onConfirm={handleConfirm}
            onCancel={() => { setPending(null); setAddError(null); }}
            isPending={addMut.isPending}
            error={addError}
          />
        )}

        {!pending && addError && (
          <p className="text-sm text-red-400 bg-red-950/30 border border-red-800/30 rounded-lg px-3 py-2">
            {addError}
          </p>
        )}
      </div>

      {/* Watchlist table */}
      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => <div key={i} className="h-12 bg-gray-800 rounded-xl animate-pulse" />)}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 bg-gray-900 border border-gray-800 rounded-2xl">
          <Search size={32} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No stocks tracked yet</p>
          <p className="text-gray-600 text-sm mt-1">Search above to add your first stock</p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Stats bar */}
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>{items.length} stock{items.length !== 1 ? "s" : ""} tracked</span>
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ["watchlist"] })}
              className="flex items-center gap-1 hover:text-gray-300 transition-colors"
            >
              <RefreshCw size={11} /> Refresh
            </button>
          </div>

          {/* Grouped by sector */}
          {sortedSectors.map(sector => (
            <SectorGroup
              key={sector}
              sector={sector}
              items={grouped[sector]}
              recentlyAdded={recentlyAdded}
              onRemove={sym => removeMut.mutate(sym)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Collapsible sector group ──────────────────────────────────────────────────
function SectorGroup({
  sector,
  items,
  recentlyAdded,
  onRemove,
}: {
  sector: string;
  items: WatchlistItem[];
  recentlyAdded: Set<string>;
  onRemove: (sym: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const dot = {
    "Technology":        "bg-blue-400",
    "Financials":        "bg-emerald-400",
    "Healthcare":        "bg-rose-400",
    "Energy":            "bg-amber-400",
    "Consumer Staples":  "bg-violet-400",
    "Consumer Discret.": "bg-orange-400",
    "Industrials":       "bg-cyan-400",
    "Materials":         "bg-lime-400",
    "Utilities":         "bg-teal-400",
    "Communication":     "bg-purple-400",
    "Real Estate":       "bg-pink-400",
  }[sector] ?? "bg-gray-600";

  return (
    <div>
      <button
        onClick={() => setCollapsed(c => !c)}
        className="w-full flex items-center gap-2 mb-2 text-left group"
      >
        <div className={cn("w-2 h-2 rounded-full", dot)} />
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider group-hover:text-gray-300 transition-colors">
          {sector}
        </span>
        <span className="text-xs text-gray-700 ml-1">({items.length})</span>
        <ChevronDown
          size={12}
          className={cn("ml-auto text-gray-700 transition-transform", collapsed && "-rotate-90")}
        />
      </button>
      {!collapsed && (
        <div className="space-y-1.5">
          {items.map(item => (
            <WatchlistRow
              key={item.id}
              item={item}
              isNew={recentlyAdded.has(item.symbol)}
              onRemove={() => onRemove(item.symbol)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
