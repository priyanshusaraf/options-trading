import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Dashboard } from "./pages/Dashboard";
import { Watchlist } from "./pages/Watchlist";
import { Analysis } from "./pages/Analysis";
import { Events } from "./pages/Events";
import { Portfolio } from "./pages/Portfolio";
import { SupplyChain } from "./pages/SupplyChain";
import Macro from "./pages/Macro";
import AlertsPage from "./pages/Alerts";
import Correlations from "./pages/Correlations";
import {
  BarChart2, List, TrendingUp, Activity,
  Calendar, Briefcase, GitBranch,
  TrendingDown, Bell, Grid,
} from "lucide-react";
import { cn } from "./lib/utils";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

type Page =
  | "dashboard"
  | "watchlist"
  | "analysis"
  | "events"
  | "portfolio"
  | "supplychain"
  | "macro"
  | "alerts"
  | "correlations";

const NAV_SECTIONS = [
  {
    label: "Markets",
    items: [
      { id: "dashboard" as Page, label: "Dashboard", icon: <BarChart2 size={15} /> },
      { id: "analysis" as Page, label: "Analysis", icon: <TrendingUp size={15} /> },
      { id: "events" as Page, label: "Event Calendar", icon: <Calendar size={15} /> },
      { id: "macro" as Page, label: "Macro Dashboard", icon: <TrendingDown size={15} /> },
      { id: "correlations" as Page, label: "Correlations", icon: <Grid size={15} /> },
    ],
  },
  {
    label: "Portfolio",
    items: [
      { id: "watchlist" as Page, label: "Watchlist", icon: <List size={15} /> },
      { id: "portfolio" as Page, label: "Holdings & PnL", icon: <Briefcase size={15} /> },
      { id: "alerts" as Page, label: "Alerts", icon: <Bell size={15} /> },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { id: "supplychain" as Page, label: "Supply Chain", icon: <GitBranch size={15} /> },
    ],
  },
];

function App() {
  const [page, setPage] = useState<Page>("dashboard");

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-surface text-slate-200 flex">
        {/* Sidebar */}
        <nav className="w-56 shrink-0 bg-surface-1 border-r border-surface-3 flex flex-col">
          <div className="px-5 py-5 border-b border-surface-3">
            <div className="flex items-center gap-2">
              <Activity size={20} className="text-accent-blue" />
              <span className="font-bold text-white text-sm">Market Intel</span>
            </div>
            <p className="text-xs text-slate-600 mt-1">Research Platform</p>
          </div>

          <div className="flex-1 p-3 space-y-4 overflow-y-auto">
            {NAV_SECTIONS.map((section) => (
              <div key={section.label}>
                <p className="text-xs text-slate-600 uppercase tracking-wider px-3 mb-1.5 font-medium">
                  {section.label}
                </p>
                <div className="space-y-0.5">
                  {section.items.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setPage(item.id)}
                      className={cn(
                        "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                        page === item.id
                          ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/25"
                          : "text-slate-400 hover:text-white hover:bg-surface-2"
                      )}
                    >
                      {item.icon}
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-surface-3 text-xs text-slate-600">
            <p>Personal research platform</p>
            <p className="mt-0.5 text-slate-700">yfinance · Finnhub · FRED · Kite</p>
          </div>
        </nav>

        {/* Main */}
        <main className="flex-1 overflow-y-auto p-8">
          {page === "dashboard" && <Dashboard />}
          {page === "analysis" && <Analysis />}
          {page === "events" && <Events />}
          {page === "watchlist" && <Watchlist />}
          {page === "portfolio" && <Portfolio />}
          {page === "supplychain" && <SupplyChain />}
          {page === "macro" && <Macro />}
          {page === "alerts" && <AlertsPage />}
          {page === "correlations" && <Correlations />}
        </main>
      </div>
    </QueryClientProvider>
  );
}

export default App;
