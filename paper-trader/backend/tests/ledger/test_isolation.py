"""The ledger is read-and-record only.

These assertions are the guardrail, not documentation: a journalling bug must
never be able to become a real-money bug.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]   # backend/


def _py(pkg: str) -> list[pathlib.Path]:
    d = ROOT / "app" / pkg
    return list(d.rglob("*.py")) if d.exists() else []


def test_the_engine_never_imports_the_ledger():
    """Runtime engine/API code stays out of the ledger implementation.

    The offline copy and restore verifiers intentionally inspect all three plane
    contracts; they are operational tooling, not runtime coupling.
    """
    cross_plane_operations = {
        ("db", "copy_contract.py"),
        ("db", "restore_contract.py"),
    }
    offenders = [
        p for p in _py("engine") + _py("api") + _py("db")
        if re.search(r"^\s*(from|import)\s+app\.ledger", p.read_text(), re.M)
        and p.name != "runner.py"
        and (p.parent.name, p.name) not in cross_plane_operations
    ]
    assert offenders == [], f"engine code importing app.ledger: {offenders}"


def test_the_ledger_never_constructs_execution_orm_rows():
    banned = re.compile(r"\b(Position|CapitalState|EquitySnapshot)\s*\(")
    offenders = [p for p in _py("ledger") if banned.search(p.read_text())]
    assert offenders == [], f"ledger code constructing execution rows: {offenders}"


def test_the_ledger_never_writes_through_a_session_add_of_execution_models():
    """app/ledger may READ app.db.models (to learn which orders are the bot's)
    but must never import a writable execution session factory."""
    offenders = [
        p for p in _py("ledger")
        if re.search(r"from\s+app\.db\.session\s+import", p.read_text())
    ]
    assert offenders == [], f"ledger importing the execution session: {offenders}"


def test_the_bot_tag_constant_agrees_with_the_live_broker():
    """classify.py deliberately does not import live_broker — that would breach
    the boundary — so the two constants are checked to agree instead."""
    from app.ledger.classify import BOT_TAG

    src = (ROOT / "app" / "engine" / "live_broker.py").read_text()
    m = re.search(r'^TAG\s*=\s*["\']([^"\']+)["\']', src, re.M)
    assert m, "could not find a module-level TAG in live_broker.py"
    assert m.group(1) == BOT_TAG, (
        f"live_broker TAG={m.group(1)!r} but classify.BOT_TAG={BOT_TAG!r} — "
        "every bot order would be misfiled as manual")


def test_the_safe_kite_allowlist_still_excludes_every_mutating_route():
    """The detector needs only reads, which were already allowlisted. If this
    fails, someone widened the safety perimeter for a journalling feature."""
    src = (ROOT / "app" / "providers" / "safe_kite.py").read_text()
    m = re.search(r"ALLOWED_ROUTES\s*[:=]\s*[^=]*?[\{\(](.*?)[\}\)]", src, re.S)
    assert m, "could not locate ALLOWED_ROUTES in safe_kite.py"
    allowed = m.group(1)
    for mutating in ("order.place", "order.modify", "order.cancel"):
        assert f'"{mutating}"' not in allowed, (
            f"{mutating} appeared in the SafePaperKite allowlist")
