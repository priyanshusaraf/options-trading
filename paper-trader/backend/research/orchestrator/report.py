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

    validated = report.get("validated", [])
    lines.append(f"## Validated candidates ({len(validated)})")
    if validated:
        for v in sorted(validated, key=lambda x: x.get("dsr", 0), reverse=True):
            lines.append(f"- **{v['instrument']}** — DSR {v['dsr']:.3f} · "
                         f"trades {v['scorecard'].get('trades')} · "
                         f"return {v['scorecard'].get('return_pct')}% · "
                         f"maxDD {v['scorecard'].get('max_drawdown_pct')}%")
    else:
        lines.append("- none cleared the validation gates")
    lines.append("")

    prom = report.get("promotion")
    lines.append("## Promotion proposal")
    lines.append(f"- {prom['instrument']} (DSR {prom['dsr']:.3f}) — queued for human review"
                 if prom else "- none")
    lines.append("")

    rejected = report.get("rejected", [])
    lines.append(f"## Rejected ({len(rejected)}) — negative evidence")
    for r in rejected:
        lines.append(f"- {r['instrument']}: {r.get('reason', '')}")
    lines.append("")

    lines.append(f"## Qualifying universe ({len(report.get('qualified', []))})")
    lines.append(", ".join(report.get("qualified", [])) or "- none")
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict, path: str) -> str:
    with open(path, "w") as f:
        f.write(render_markdown(report))
    return path
