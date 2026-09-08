"""Morning research report — the human-facing output of an experiment. Renders the
report dict from `run_experiment` into markdown: what was tested, what qualified,
what was rejected and WHY, the validated candidates with their scorecards, and the
promotion proposal (if any). Negative results are shown as prominently as positive
ones — that is the point.
"""
from __future__ import annotations


def _render_explanation(ex: dict) -> list[str]:
    """The 'how this strategy works' block — thesis + primitives + the numbered rules
    with the live parameters, so a human can judge the logic, not just the score."""
    lines = ["## How this strategy works",
             f"**{ex.get('display_name', '')}** — `{ex.get('strategy_key', '')}`", "",
             f"**Thesis:** {ex.get('thesis', '')}", ""]
    prim = ex.get("primitives") or []
    if prim:
        lines += ["**Primitives:** " + " · ".join(prim), ""]
    lines.append("**Logic (with this run's parameters):**")
    lines += [f"{i}. {r}" for i, r in enumerate(ex.get("rules", []), 1)]
    lines.append("")
    if ex.get("note"):
        lines += [f"> {ex['note']}", ""]
    if ex.get("caveats"):
        lines += [f"_Not modelled: {ex['caveats']}_", ""]
    return lines


def _render_validated(validated: list[dict]) -> list[str]:
    lines = [f"## Validated candidates ({len(validated)})"]
    if not validated:
        return lines + ["- none cleared the validation gates", ""]
    for candidate in sorted(validated, key=lambda row: row.get("dsr", 0), reverse=True):
        lines.append(
            f"- **{candidate['instrument']}** — DSR {candidate['dsr']:.3f} · "
            f"breadth-adjusted {candidate.get('dsr_breadth_deflated', candidate['dsr']):.3f} · "
            f"trades {candidate['scorecard'].get('trades')} · "
            f"return {candidate['scorecard'].get('return_pct')}% · "
            f"maxDD {candidate['scorecard'].get('max_drawdown_pct')}%"
        )
    return lines + [""]


def _render_promotion(promotion: dict | None) -> list[str]:
    if promotion is None:
        return ["## Promotion proposal", "- none", ""]
    adjusted = promotion.get("dsr_breadth_deflated", promotion["dsr"])
    return [
        "## Promotion proposal",
        f"- {promotion['instrument']} (raw holdout DSR {promotion['dsr']:.3f}; "
        f"breadth-adjusted {adjusted:.3f}) — selected on this holdout, so this "
        "estimate is selection-affected; queued for an untouched shadow period, "
        "not treated as independent confirmation",
        "",
    ]


def _render_context(report: dict) -> list[str]:
    lines = []
    regimes = report.get("regimes") or {}
    if regimes:
        lines.extend([
            "## Market regimes in this sample",
            "Which conditions the result was measured in. An edge that lives in one "
            "regime is invisible in an aggregate statistic — and is a good strategy "
            "with a missing filter, not a mediocre one.", "",
            "| instrument | trend_hi | trend_lo | chop_hi | chop_lo | unknown |",
            "|---|---|---|---|---|---|",
        ])
        for key in sorted(regimes):
            distribution = regimes[key]
            lines.append(f"| {key} | " + " | ".join(
                str(distribution.get(role, 0)) for role in
                ("trend_hi", "trend_lo", "chop_hi", "chop_lo", "unknown")) + " |")
        lines.append("")
    edge = report.get("edge_map", "")
    if edge:
        lines.extend(["## Block edge map — which idea works where", edge, ""])
    suppressed = report.get("suppressed_blocks") or []
    if suppressed:
        lines.extend([
            f"## Suppressed this run ({len(suppressed)})",
            "Families with a well-powered negative record on this universe. Skipped, "
            "never banned — later evidence lets them back in.",
            ", ".join(sorted(suppressed)), "",
        ])
    return lines


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Research report")
    lines.append("")
    lines.append(f"- **Program:** {report.get('program', '')}")
    lines.append(f"- **Hypothesis:** {report.get('hypothesis', '')}")
    lines.append(f"- **Spec:** `{report.get('spec_id', '')}`  ·  "
                 f"commit `{report.get('git_commit', '')}`  ·  run #{report.get('run_id', '')}")
    lines.append(f"- **Decision:** {report.get('decision', '')}  ·  "
                 f"bars evaluated: {report.get('total_bars', 0)}")
    lines.append("")

    if report.get("explanation"):
        lines.extend(_render_explanation(report["explanation"]))

    lines.extend(_render_validated(report.get("validated", [])))
    lines.extend(_render_promotion(report.get("promotion")))

    rejected = report.get("rejected", [])
    lines.append(f"## Rejected ({len(rejected)}) — negative evidence")
    for r in rejected:
        lines.append(f"- {r['instrument']}: {r.get('reason', '')}")
    lines.append("")

    lines.append(f"## Qualifying universe ({len(report.get('qualified', []))})")
    lines.append(", ".join(report.get("qualified", [])) or "- none")
    lines.append("")

    lines.extend(_render_context(report))
    return "\n".join(lines)


def write_report(report: dict, path: str) -> str:
    with open(path, "w") as f:
        f.write(render_markdown(report))
    return path
