"""Visual groups share the sparse layout revision without entering graph JSON."""
from __future__ import annotations

import pytest

from app.db.session import init_db
from app.editor import layouts
from app.ir.strategies.expanding_z import GRAPH


IDENTIFIER = GRAPH["identifier"]
VERSION = GRAPH["version"]
AUTHORED_IDS = frozenset(node["instance_id"] for node in GRAPH["nodes"])


@pytest.fixture(autouse=True)
def _db():
    init_db(reset=True)


def _group(*members: str) -> layouts.VisualGroup:
    return layouts.VisualGroup(
        "g_signal",
        "Signal",
        layouts.GroupFrame(10.0, 20.0, 300.0, 180.0),
        False,
        tuple(members),
    )


def test_visual_groups_round_trip_and_preserve_sparse_positions():
    positioned = layouts.save_layout(
        IDENTIFIER,
        VERSION,
        base_revision=0,
        positions=(layouts.Position("n_ema", 12.0, 24.0),),
    )

    grouped = layouts.save_groups(
        IDENTIFIER,
        VERSION,
        base_revision=positioned.revision,
        groups=(_group("n_ema", "n_impulse"),),
        valid_instance_ids=AUTHORED_IDS,
    )
    loaded = layouts.load_layout(
        IDENTIFIER, VERSION, valid_instance_ids=AUTHORED_IDS
    )

    assert grouped.revision == 2
    assert grouped.positions == (layouts.Position("n_ema", 12.0, 24.0),)
    assert grouped.groups == (_group("n_ema", "n_impulse"),)
    assert loaded == grouped


def test_visual_group_members_must_be_current_authored_nodes():
    with pytest.raises(layouts.LayoutRejected, match="unknown or derived"):
        layouts.save_groups(
            IDENTIFIER,
            VERSION,
            base_revision=0,
            groups=(_group("n_atr/n_internal"),),
            valid_instance_ids=AUTHORED_IDS,
        )
