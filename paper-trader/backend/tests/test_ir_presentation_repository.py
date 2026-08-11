"""Visual groups share the sparse layout revision without entering graph JSON."""
from __future__ import annotations

import pytest

from app.db.session import SessionLocal, init_db
from app.db.models import LEGACY_OWNER_ID
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
        owner_id=LEGACY_OWNER_ID,
    )

    grouped = layouts.save_groups(
        IDENTIFIER,
        VERSION,
        base_revision=positioned.revision,
        groups=(_group("n_ema", "n_impulse"),),
        valid_instance_ids=AUTHORED_IDS,
        owner_id=LEGACY_OWNER_ID,
    )
    loaded = layouts.load_layout(
        IDENTIFIER, VERSION, valid_instance_ids=AUTHORED_IDS, owner_id=LEGACY_OWNER_ID
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
            owner_id=LEGACY_OWNER_ID,
        )


def test_presentation_batch_returns_exact_forward_and_inverse_operations():
    operations = (
        {
            "operation": "create_group",
            "identifier": "g_signal",
            "display_name": "Signal",
            "members": ["n_ema"],
            "frame": {"x": 10, "y": 20, "width": 300, "height": 180},
            "collapsed": False,
        },
        {
            "operation": "rename_group",
            "identifier": "g_signal",
            "display_name": "Renamed",
        },
        {
            "operation": "add_group_member",
            "identifier": "g_signal",
            "instance_id": "n_impulse",
        },
        {
            "operation": "set_group_collapsed",
            "identifier": "g_signal",
            "collapsed": True,
        },
    )

    with SessionLocal.begin() as session:
        result, delta = layouts.apply_presentation_batch_in_session(
            session,
            IDENTIFIER,
            VERSION,
            base_revision=0,
            operations=operations,
            valid_instance_ids=AUTHORED_IDS,
            owner_id=LEGACY_OWNER_ID,
        )

    assert result.revision == 1
    assert result.groups[0].display_name == "Renamed"
    assert result.groups[0].members == ("n_ema", "n_impulse")
    assert result.groups[0].collapsed is True
    assert delta.forward_operations[0]["operation"] == "create_group"
    assert [item["operation"] for item in delta.inverse_operations] == [
        "set_group_collapsed",
        "remove_group_member",
        "rename_group",
        "remove_group",
    ]

    with SessionLocal.begin() as session:
        restored, _ = layouts.apply_presentation_batch_in_session(
            session,
            IDENTIFIER,
            VERSION,
            base_revision=1,
            operations=delta.inverse_operations,
            valid_instance_ids=AUTHORED_IDS,
            owner_id=LEGACY_OWNER_ID,
        )
    assert restored.groups == ()


def test_rejected_presentation_batch_does_not_advance_revision():
    with pytest.raises(layouts.LayoutRejected):
        with SessionLocal.begin() as session:
            layouts.apply_presentation_batch_in_session(
                session,
                IDENTIFIER,
                VERSION,
                base_revision=0,
                operations=({
                    "operation": "create_group",
                    "identifier": "g_signal",
                    "display_name": "Signal",
                    "members": ["n_ema", "n_missing"],
                    "frame": {"x": 10, "y": 20, "width": 300, "height": 180},
                    "collapsed": False,
                },),
                valid_instance_ids=AUTHORED_IDS,
                owner_id=LEGACY_OWNER_ID,
            )

    assert layouts.load_layout(
        IDENTIFIER, VERSION, valid_instance_ids=AUTHORED_IDS, owner_id=LEGACY_OWNER_ID
    ).revision == 0
