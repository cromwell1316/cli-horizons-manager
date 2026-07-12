"""Verification tests for H50 horizon time-machine snapshots."""

from pathlib import Path
import tempfile

from horizon_manager.history import (
    build_snapshot,
    diff_snapshots,
    list_snapshots,
    read_snapshot,
    summarize_since_last,
    write_snapshot,
)


def _state(status_h40: str = "planned", status_h41: str = "planned") -> dict:
    return {
        "horizons": [
            {"id": "H40", "title": "Conflict Radar", "status": status_h40, "wave": 8},
            {"id": "H41", "title": "Conflict UI", "status": status_h41, "wave": 8},
        ],
        "schema_version": 1,
    }


def _conflicts(blocking: bool = False) -> dict:
    return {
        "conflicts": [
            {
                "left": "H40",
                "right": "H41",
                "kind": "write_write",
                "severity": "block" if blocking else "info",
            }
        ]
    }


def _locks(active: bool = True) -> dict:
    return {
        "locks": [
            {
                "horizon_id": "H41",
                "agent_id": "agent-a",
                "status": "active" if active else "released",
            }
        ]
    }


def _next(*ids: str) -> dict:
    return {"recommendations": [{"horizon_id": horizon_id, "rank": index + 1} for index, horizon_id in enumerate(ids)]}


def test_snapshot_serializes_deterministic_json(tmp_path: Path) -> None:
    snapshot = build_snapshot(
        state=_state(),
        conflicts=_conflicts(),
        locks=_locks(),
        recommendations=_next("H40"),
        events=[{"event_id": "e1"}],
        dashboard="<html>one</html>",
        created_at="2026-07-12T00:00:00Z",
    )
    first_path = write_snapshot(tmp_path, snapshot)
    second_path = write_snapshot(tmp_path, snapshot)
    assert first_path == second_path
    assert first_path.read_text(encoding="utf-8") == snapshot.to_json()
    assert read_snapshot(first_path).to_dict() == snapshot.to_dict()
    assert '"snapshot_id":' in first_path.read_text(encoding="utf-8")


def test_diff_reports_status_transition_and_start_now_changes() -> None:
    previous = build_snapshot(
        state=_state(status_h40="planned"),
        recommendations=_next("H40"),
        created_at="2026-07-12T00:00:00Z",
    )
    current = build_snapshot(
        state=_state(status_h40="implemented"),
        recommendations=_next("H41"),
        created_at="2026-07-12T00:01:00Z",
    )
    changes = diff_snapshots(previous, current)
    assert changes.status_transitions == ({"horizon_id": "H40", "from": "planned", "to": "implemented"},)
    assert changes.new_recommendations == ("H41",)
    assert changes.removed_recommendations == ("H40",)


def test_diff_reports_new_conflicts_blockers_and_resolved_locks() -> None:
    previous = build_snapshot(
        state=_state(),
        conflicts=_conflicts(blocking=False),
        locks=_locks(active=True),
        created_at="2026-07-12T00:00:00Z",
    )
    current = build_snapshot(
        state=_state(),
        conflicts=_conflicts(blocking=True),
        locks=_locks(active=False),
        created_at="2026-07-12T00:01:00Z",
    )
    changes = diff_snapshots(previous, current)
    assert changes.new_conflicts == ({"left": "H40", "right": "H41", "kind": "write_write", "severity": "block"},)
    assert changes.new_blockers == (
        {"horizon_id": "H40", "value": "conflict:H41"},
        {"horizon_id": "H41", "value": "conflict:H40"},
    )
    assert changes.resolved_locks == ({"horizon_id": "H41", "agent_id": "agent-a", "status": "active"},)
    assert changes.new_locks == ({"horizon_id": "H41", "agent_id": "agent-a", "status": "released"},)


def test_malformed_snapshots_are_diagnosed_safely(tmp_path: Path) -> None:
    valid = build_snapshot(state=_state(), created_at="2026-07-12T00:00:00Z")
    write_snapshot(tmp_path, valid)
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    index = list_snapshots(tmp_path)
    assert len(index.snapshots) == 1
    assert len(index.diagnostics) == 1
    assert "invalid snapshot" in index.diagnostics[0]


def test_summarize_since_last_uses_latest_prior_snapshot(tmp_path: Path) -> None:
    previous = build_snapshot(state=_state(), events=[{"event_id": "e1"}], created_at="2026-07-12T00:00:00Z")
    current = build_snapshot(
        state=_state(status_h41="implemented"),
        events=[{"event_id": "e1"}, {"event_id": "e2"}],
        created_at="2026-07-12T00:01:00Z",
    )
    write_snapshot(tmp_path, previous)
    changes = summarize_since_last(tmp_path, current)
    assert changes.status_transitions == ({"horizon_id": "H41", "from": "planned", "to": "implemented"},)
    assert changes.event_delta == 1
    assert changes.new_event_ids == ("e2",)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as raw:
        test_snapshot_serializes_deterministic_json(Path(raw))
    test_diff_reports_status_transition_and_start_now_changes()
    test_diff_reports_new_conflicts_blockers_and_resolved_locks()
    with tempfile.TemporaryDirectory() as raw:
        test_malformed_snapshots_are_diagnosed_safely(Path(raw))
    with tempfile.TemporaryDirectory() as raw:
        test_summarize_since_last_uses_latest_prior_snapshot(Path(raw))
