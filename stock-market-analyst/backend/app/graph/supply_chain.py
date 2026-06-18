"""
Supply Chain + Dependency Graph Engine.

Graph schema:
  Nodes:
    - Company    (symbol, sector)
    - Commodity  (name, category)
    - Region     (name, geopolitical_risk_score)
    - Sector     (name)

  Edges:
    - company → supplier (company)        [SUPPLIES_TO, weight=revenue_share]
    - company → commodity                 [DEPENDS_ON, weight=cost_share]
    - commodity → region                  [PRODUCED_IN, weight=production_pct]
    - company → sector                    [PART_OF]

Built from:
  1. Annual report PDF parsing (pdfplumber)
  2. Finnhub company peers
  3. FMP supply chain data (if available)
  4. Hardcoded NSE sector maps

Analysis:
  - Disruption simulation: propagate shock from any node
  - Dependency risk score per company
  - Identify clusters and critical path nodes
  - Export to JSON for frontend D3/Sigma.js visualization
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import networkx as nx
import numpy as np

from backend.app.core.config import get_settings
from backend.app.core.logging import logger


# ── Node / Edge types ─────────────────────────────────────────────────────────

@dataclass
class CompanyNode:
    symbol: str
    name: str
    sector: str
    market_cap: Optional[float] = None
    country: str = "India"


@dataclass
class CommodityNode:
    name: str
    category: str          # energy / metals / agriculture / chemicals
    primary_region: str    # Where it's primarily produced


@dataclass
class DisruptionResult:
    source_node: str
    shock_magnitude: float
    affected_companies: dict[str, float]   # symbol → impact_score (0–1)
    propagation_path: list[str]
    total_affected: int
    description: str


# ── Pre-built sector dependency knowledge base ─────────────────────────────────

SECTOR_COMMODITY_DEPS: dict[str, list[tuple[str, float]]] = {
    # sector → [(commodity, cost_share)]
    "energy":            [("crude_oil", 0.7), ("natural_gas", 0.3)],
    "chemicals":         [("crude_oil", 0.5), ("natural_gas", 0.3), ("coal", 0.2)],
    "airlines":          [("crude_oil", 0.4), ("jet_fuel", 0.4)],
    "auto":              [("steel", 0.3), ("aluminum", 0.2), ("rubber", 0.15), ("semiconductors", 0.2)],
    "fmcg":              [("palm_oil", 0.2), ("wheat", 0.15), ("sugar", 0.1), ("packaging", 0.2)],
    "metals":            [("iron_ore", 0.5), ("coking_coal", 0.3), ("electricity", 0.2)],
    "cement":            [("limestone", 0.3), ("coal", 0.25), ("electricity", 0.2)],
    "technology":        [("semiconductors", 0.4), ("rare_earths", 0.15)],
    "pharma":            [("apis", 0.4), ("chemicals", 0.3)],
    "textile":           [("cotton", 0.4), ("polyester", 0.3)],
    "agriculture":       [("fertilizers", 0.3), ("water", 0.2), ("seeds", 0.2)],
    "infrastructure":    [("steel", 0.4), ("cement", 0.3), ("copper", 0.15)],
    "logistics":         [("crude_oil", 0.5), ("natural_gas", 0.2)],
    "banking":           [],
    "real_estate":       [("steel", 0.2), ("cement", 0.3), ("copper", 0.1)],
}

COMMODITY_REGION: dict[str, list[tuple[str, float]]] = {
    "crude_oil":      [("Middle East", 0.45), ("Russia", 0.15), ("US", 0.15), ("Others", 0.25)],
    "natural_gas":    [("Russia", 0.20), ("Middle East", 0.25), ("US", 0.20), ("Others", 0.35)],
    "iron_ore":       [("Australia", 0.55), ("Brazil", 0.25), ("Others", 0.20)],
    "coking_coal":    [("Australia", 0.50), ("Russia", 0.15), ("US", 0.15), ("Others", 0.20)],
    "semiconductors": [("Taiwan", 0.45), ("South Korea", 0.20), ("US", 0.15), ("Others", 0.20)],
    "rare_earths":    [("China", 0.65), ("Australia", 0.15), ("Others", 0.20)],
    "palm_oil":       [("Indonesia", 0.55), ("Malaysia", 0.35), ("Others", 0.10)],
    "cotton":         [("India", 0.25), ("China", 0.25), ("US", 0.20), ("Others", 0.30)],
    "wheat":          [("Russia", 0.20), ("EU", 0.15), ("US", 0.15), ("India", 0.15), ("Others", 0.35)],
    "copper":         [("Chile", 0.30), ("Peru", 0.10), ("DRC", 0.10), ("Others", 0.50)],
    "aluminum":       [("China", 0.55), ("Russia", 0.10), ("Others", 0.35)],
    "steel":          [("China", 0.55), ("India", 0.10), ("Others", 0.35)],
    "sugar":          [("Brazil", 0.30), ("India", 0.20), ("EU", 0.15), ("Others", 0.35)],
    "rubber":         [("Thailand", 0.35), ("Indonesia", 0.25), ("Others", 0.40)],
}

REGION_RISK: dict[str, float] = {
    "Middle East": 0.7,
    "Russia": 0.8,
    "China": 0.6,
    "Taiwan": 0.65,
    "South Korea": 0.3,
    "US": 0.2,
    "EU": 0.25,
    "Australia": 0.15,
    "Brazil": 0.35,
    "India": 0.3,
    "Indonesia": 0.35,
    "Malaysia": 0.25,
    "Others": 0.4,
}


class SupplyChainGraph:
    """
    Manages a NetworkX DiGraph of companies, commodities, and regions.
    Supports disruption simulation and risk scoring.
    """

    def __init__(self):
        self.G = nx.DiGraph()
        self._build_commodity_region_base()

    # ── Build / extend graph ──────────────────────────────────────────────────

    def _build_commodity_region_base(self) -> None:
        """Initialize the commodity → region edges from the knowledge base."""
        for commodity, regions in COMMODITY_REGION.items():
            self.G.add_node(commodity, node_type="commodity")
            for region, weight in regions:
                self.G.add_node(region, node_type="region",
                                geopolitical_risk=REGION_RISK.get(region, 0.4))
                self.G.add_edge(
                    commodity, region,
                    edge_type="PRODUCED_IN",
                    weight=weight,
                )

    def add_company(self, company: CompanyNode) -> None:
        """Add a company and wire up its sector's commodity dependencies."""
        self.G.add_node(
            company.symbol,
            node_type="company",
            name=company.name,
            sector=company.sector,
            market_cap=company.market_cap or 0,
            country=company.country,
        )
        self.G.add_node(company.sector, node_type="sector")
        self.G.add_edge(company.symbol, company.sector, edge_type="PART_OF", weight=1.0)

        # Wire sector commodity dependencies
        for commodity, share in SECTOR_COMMODITY_DEPS.get(company.sector, []):
            if commodity not in self.G.nodes:
                self.G.add_node(commodity, node_type="commodity")
            self.G.add_edge(
                company.symbol, commodity,
                edge_type="DEPENDS_ON",
                weight=share,
            )

    def add_supplier_edge(
        self,
        customer_symbol: str,
        supplier_symbol: str,
        revenue_share: float = 0.1,
        description: str = "",
    ) -> None:
        """Add a direct company-to-company supply relationship."""
        self.G.add_edge(
            supplier_symbol, customer_symbol,
            edge_type="SUPPLIES_TO",
            weight=revenue_share,
            description=description,
        )

    def add_companies_from_watchlist(
        self, items: list[dict]
    ) -> None:
        """
        Bulk-add companies from watchlist.
        items: [{symbol, name, sector, market_cap}]
        """
        for item in items:
            node = CompanyNode(
                symbol=item["symbol"],
                name=item.get("name", item["symbol"]),
                sector=item.get("sector", "unknown"),
                market_cap=item.get("market_cap"),
                country=item.get("country", "India"),
            )
            self.add_company(node)

    # ── Disruption simulation ─────────────────────────────────────────────────

    def simulate_disruption(
        self,
        source_node: str,
        shock_magnitude: float = 0.5,
        max_hops: int = 4,
    ) -> DisruptionResult:
        """
        Propagate a shock from source_node through the graph.
        Impact decays with each hop and is modulated by edge weight.

        Example: simulate_disruption("crude_oil", 0.8)
          → which companies are affected, by how much?
        """
        if source_node not in self.G.nodes:
            return DisruptionResult(
                source_node=source_node,
                shock_magnitude=shock_magnitude,
                affected_companies={},
                propagation_path=[source_node],
                total_affected=0,
                description=f"Node '{source_node}' not found in graph.",
            )

        affected: dict[str, float] = {}
        propagation_path: list[str] = [source_node]
        queue: list[tuple[str, float, int]] = [(source_node, shock_magnitude, 0)]
        visited = {source_node}
        decay = 0.6   # Impact multiplier per hop

        while queue:
            node, impact, depth = queue.pop(0)
            if depth >= max_hops:
                continue

            # Find all nodes that DEPEND ON or are SUPPLIED BY this node
            # Traverse reverse edges: who depends on this node?
            for predecessor in self.G.predecessors(node):
                edge = self.G.edges[predecessor, node]
                edge_weight = edge.get("weight", 0.5)
                child_impact = impact * decay * edge_weight

                if predecessor not in visited and child_impact > 0.02:
                    visited.add(predecessor)
                    propagation_path.append(predecessor)
                    node_data = self.G.nodes.get(predecessor, {})
                    if node_data.get("node_type") == "company":
                        affected[predecessor] = round(child_impact, 4)
                    queue.append((predecessor, child_impact, depth + 1))

        description = self._disruption_description(source_node, shock_magnitude, affected)

        return DisruptionResult(
            source_node=source_node,
            shock_magnitude=shock_magnitude,
            affected_companies=dict(sorted(affected.items(), key=lambda x: -x[1])),
            propagation_path=propagation_path,
            total_affected=len(affected),
            description=description,
        )

    def company_risk_score(self, symbol: str) -> dict:
        """
        Compute a supply chain risk score for a company based on:
        - Geopolitical risk of commodity-producing regions it depends on
        - Number of single-source commodities (concentration risk)
        - Depth in supply chain
        """
        if symbol not in self.G.nodes:
            return {"score": 0.0, "details": {}}

        commodity_deps = [
            (n, self.G.edges[symbol, n].get("weight", 0))
            for n in self.G.successors(symbol)
            if self.G.nodes[n].get("node_type") == "commodity"
        ]

        if not commodity_deps:
            return {"score": 0.0, "details": {"message": "No commodity dependencies found"}}

        region_risks = []
        for commodity, dep_weight in commodity_deps:
            for region in self.G.successors(commodity):
                if self.G.nodes[region].get("node_type") == "region":
                    geo_risk = self.G.nodes[region].get("geopolitical_risk", 0.4)
                    prod_weight = self.G.edges[commodity, region].get("weight", 0.25)
                    region_risks.append(geo_risk * prod_weight * dep_weight)

        geo_risk_score = float(np.mean(region_risks)) if region_risks else 0.0
        concentration = 1.0 / len(commodity_deps)  # Higher if fewer commodities
        final_score = min(geo_risk_score * 0.7 + concentration * 0.3, 1.0)

        return {
            "score": round(final_score, 3),
            "details": {
                "commodity_dependencies": len(commodity_deps),
                "geo_risk_avg": round(geo_risk_score, 3),
                "concentration_risk": round(concentration, 3),
                "commodities": [
                    {"commodity": c, "weight": round(w, 3)} for c, w in commodity_deps
                ],
            },
        }

    # ── Export ────────────────────────────────────────────────────────────────

    def to_json(self, include_types: Optional[list[str]] = None) -> dict:
        """
        Export graph as JSON for frontend visualization (D3/Sigma.js).
        include_types: filter by node_type ("company", "commodity", "region", "sector")
        """
        nodes = []
        for node_id, data in self.G.nodes(data=True):
            ntype = data.get("node_type", "unknown")
            if include_types and ntype not in include_types:
                continue
            nodes.append({
                "id": node_id,
                "type": ntype,
                "label": data.get("name", node_id),
                **{k: v for k, v in data.items() if k != "name"},
            })

        edges = []
        for src, tgt, data in self.G.edges(data=True):
            src_type = self.G.nodes[src].get("node_type", "")
            tgt_type = self.G.nodes[tgt].get("node_type", "")
            if include_types and (src_type not in include_types or tgt_type not in include_types):
                continue
            edges.append({
                "source": src,
                "target": tgt,
                "type": data.get("edge_type", "UNKNOWN"),
                "weight": data.get("weight", 1.0),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "companies": sum(1 for n in nodes if n["type"] == "company"),
                "commodities": sum(1 for n in nodes if n["type"] == "commodity"),
                "regions": sum(1 for n in nodes if n["type"] == "region"),
            },
        }

    def find_critical_nodes(self, node_type: str = "commodity") -> list[dict]:
        """
        Identify nodes with the highest betweenness centrality —
        these are the critical dependencies where disruption propagates most.
        """
        sub = nx.subgraph(
            self.G,
            [n for n, d in self.G.nodes(data=True) if d.get("node_type") == node_type
             or d.get("node_type") == "company"],
        )
        if len(sub) < 2:
            return []
        centrality = nx.betweenness_centrality(sub)
        ranked = sorted(centrality.items(), key=lambda x: -x[1])
        return [
            {"node": n, "centrality": round(c, 4), "type": self.G.nodes[n].get("node_type")}
            for n, c in ranked[:10]
        ]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _disruption_description(
        self, source: str, magnitude: float, affected: dict[str, float]
    ) -> str:
        if not affected:
            return f"Shock at '{source}' (magnitude={magnitude:.0%}) — no downstream companies affected."
        top = list(affected.items())[:3]
        companies = ", ".join(f"{s} ({v:.0%})" for s, v in top)
        return (
            f"Shock at '{source}' (magnitude={magnitude:.0%}) affects "
            f"{len(affected)} companies. Most impacted: {companies}."
        )
