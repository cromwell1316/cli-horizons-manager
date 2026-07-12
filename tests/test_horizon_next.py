"""Tests for H43 horizon next-engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.conflicts import build_conflict_matrix  # noqa: E402
from horizon_manager.doctor import Diagnostic, DoctorReport, Severity  # noqa: E402
from horizon_manager.model import (  # noqa: E402
    HorizonDependency,
    HorizonRecord,
    HorizonState,
    HorizonStatus,
    OwnedPath,
    OwnedPathMode,
)
from horizon_manager.next import ExclusionReason, explain_recommendation, recommend_next  # noqa: E402
from horizon_manager.parser import parse_horizon_tree  # noqa: E402


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def test_ready_horizon_is_ranked_and_serializes_deterministically() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H43", "Next", HorizonStatus.PLANNED, "src/next.py", deps=("H39",)),
        ),
        generated_from="fixture",
    )

    report = recommend_next(state, now=NOW)

    assert [item.horizon_id for item in report.recommendations] == ["H43"]
    assert report.excluded[0].horizon_id == "H39"
    assert ExclusionReason.NOT_PLANNED.value in report.excluded[0].reasons
    assert json.loads(report.to_json()) == json.loads(report.to_json())
    assert report.recommendations[0].score.to_dict().keys() == {
        "readiness",
        "lock_available",
        "conflict_safety",
        "unblock_value",
        "wave_priority",
        "blast_radius",
        "total",
    }
    assert "dependencies are implemented" in report.recommendations[0].explanation


def test_dependency_doctor_lock_and_conflict_blockers_exclude_horizons() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H40", "Doctor", HorizonStatus.PLANNED, "src/doctor.py", deps=("H39",)),
            _record("H43", "Next", HorizonStatus.PLANNED, "src/next.py", deps=("H42",)),
            _record("H44", "Events", HorizonStatus.PLANNED, "src/events.py", deps=("H39",)),
            _record("H45", "CLI", HorizonStatus.PLANNED, "src/shared.py", deps=("H39",)),
            _record("H46", "Gate", HorizonStatus.PLANNED, "src/shared.py", deps=("H39",)),
        )
    )
    conflicts = build_conflict_matrix(state)
    doctor = {"diagnostics": [{"horizon_id": "H40", "severity": "error", "code": "missing_contract"}]}
    locks = {
        "locks": [
            {"horizon_id": "H44", "agent_id": "agent-a", "status": "active"},
            {"horizon_id": "H46", "agent_id": "agent-b", "status": "active"},
        ]
    }

    report = recommend_next(state, doctor, conflicts, locks, now=NOW)
    excluded = {item.horizon_id: item for item in report.excluded}

    assert ExclusionReason.DOCTOR_BLOCKER.value in excluded["H40"].reasons
    assert ExclusionReason.DEPENDENCY_NOT_READY.value in excluded["H43"].reasons
    assert ExclusionReason.ACTIVE_LOCK.value in excluded["H44"].reasons
    assert ExclusionReason.ACTIVE_CONFLICT.value in excluded["H45"].reasons
    assert "H46" not in [item.horizon_id for item in report.recommendations]


def test_real_doctor_report_errors_exclude_horizon() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H43", "Next", HorizonStatus.PLANNED, "src/next.py", deps=("H39",)),
        )
    )
    doctor = DoctorReport(
        diagnostics=(
            Diagnostic(
                code="missing_owned_files",
                severity=Severity.ERROR,
                horizon_id="H43",
                message="fixture",
            ),
        ),
        horizon_count=2,
        edge_count=1,
    )

    report = recommend_next(state, doctor_report=doctor, now=NOW)

    excluded = {item.horizon_id: item for item in report.excluded}
    assert ExclusionReason.DOCTOR_BLOCKER.value in excluded["H43"].reasons


def test_unblock_value_and_blast_radius_influence_ordering() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H50", "Broad", HorizonStatus.PLANNED, "src/broad.py", deps=("H39",), wave=9),
            _record("H51", "Consumer A", HorizonStatus.PLANNED, "src/a.py", deps=("H50",), wave=10),
            _record("H52", "Consumer B", HorizonStatus.PLANNED, "src/b.py", deps=("H50",), wave=10),
            _record(
                "H53",
                "Wide Blast",
                HorizonStatus.PLANNED,
                "src/wide.py",
                deps=("H39",),
                wave=9,
                owned=(OwnedPath("src/wide.py", OwnedPathMode.EXCLUSIVE), OwnedPath("generated/state.json", OwnedPathMode.GENERATED)),
            ),
        )
    )

    report = recommend_next(state, now=NOW)

    assert report.recommendations[0].horizon_id == "H50"
    assert report.recommendations[0].score.unblock_value > report.recommendations[1].score.unblock_value
    assert report.recommendations[0].score.blast_radius > report.recommendations[1].score.blast_radius


def test_tie_breaking_uses_wave_depth_and_horizon_id() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H47", "Later", HorizonStatus.PLANNED, "src/later.py", deps=("H39",), wave=9),
            _record("H45", "First", HorizonStatus.PLANNED, "src/first.py", deps=("H39",), wave=8),
            _record("H46", "Second", HorizonStatus.PLANNED, "src/second.py", deps=("H39",), wave=8),
        )
    )

    report = recommend_next(state, now=NOW)

    assert [item.horizon_id for item in report.recommendations] == ["H45", "H46", "H47"]


def test_expired_locks_do_not_block_recommendations() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H43", "Next", HorizonStatus.PLANNED, "src/next.py", deps=("H39",)),
        )
    )
    locks = {"locks": [{"horizon_id": "H43", "agent_id": "agent-a", "expires_at": (NOW - timedelta(minutes=1)).isoformat()}]}

    report = recommend_next(state, locks=locks, now=NOW)

    assert [item.horizon_id for item in report.recommendations] == ["H43"]


def test_explain_recommendation_is_human_readable() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", HorizonStatus.IMPLEMENTED, "src/model.py"),
            _record("H43", "Next", HorizonStatus.PLANNED, "src/next.py", deps=("H39",)),
        )
    )
    recommendation = recommend_next(state, now=NOW).recommendations[0]

    assert explain_recommendation(recommendation).startswith("#1 H43 is ready")


def test_real_horizon_tree_produces_stable_report() -> None:
    state = parse_horizon_tree(ROOT / "management/subprojects/hermes-consistency-orchestrator/horizons")
    conflicts = build_conflict_matrix(state)

    report = recommend_next(state, conflict_matrix=conflicts, now=NOW, limit=5)
    data = json.loads(report.to_json())

    assert data["schema_version"] == 1
    assert data["generated_at"] == "2026-07-11T12:00:00Z"
    assert data["recommendation_count"] <= 5
    assert data["metadata"]["horizon_count"] == len(state.records)


def _record(
    horizon_id: str,
    title: str,
    status: HorizonStatus,
    path: str,
    *,
    deps: tuple[str, ...] = (),
    wave: int = 8,
    owned: tuple[OwnedPath, ...] | None = None,
) -> HorizonRecord:
    return HorizonRecord(
        id=horizon_id,
        title=title,
        directory=f"horizons/{horizon_id}",
        source_path=f"horizons/{horizon_id}/README.md",
        status=status,
        wave=wave,
        dependencies=tuple(HorizonDependency(dep, "after", f"after {dep}") for dep in deps),
        owned_files=owned or (OwnedPath(path, OwnedPathMode.EXCLUSIVE),),
        concurrency="fixture",
    )


if __name__ == "__main__":
    test_ready_horizon_is_ranked_and_serializes_deterministically()
    test_dependency_doctor_lock_and_conflict_blockers_exclude_horizons()
    test_real_doctor_report_errors_exclude_horizon()
    test_unblock_value_and_blast_radius_influence_ordering()
    test_tie_breaking_uses_wave_depth_and_horizon_id()
    test_expired_locks_do_not_block_recommendations()
    test_explain_recommendation_is_human_readable()
    test_real_horizon_tree_produces_stable_report()
