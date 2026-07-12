"""Tests for H41 horizon conflict radar."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.conflicts import (  # noqa: E402
    ConflictKind,
    ConflictSeverity,
    build_conflict_matrix,
)
from horizon_manager.model import (  # noqa: E402
    HorizonDependency,
    HorizonRecord,
    HorizonState,
    OwnedPath,
    OwnedPathMode,
)
from horizon_manager.parser import parse_horizon_tree  # noqa: E402


def test_write_write_overlap_blocks_pair() -> None:
    state = HorizonState(
        records=(
            _record("H41", "Conflict Radar", "src/shared.py", OwnedPathMode.EXCLUSIVE),
            _record("H42", "Locks", "src/shared.py", OwnedPathMode.EXCLUSIVE),
            _record("H43", "Next", "src/disjoint.py", OwnedPathMode.EXCLUSIVE),
        ),
        generated_from="fixture",
    )

    matrix = build_conflict_matrix(state)

    conflicts = matrix.conflicts
    assert len(conflicts) == 1
    assert conflicts[0].pair == ("H41", "H42")
    assert conflicts[0].kind is ConflictKind.WRITE_WRITE
    assert conflicts[0].severity is ConflictSeverity.BLOCK
    assert matrix.cannot_run_with("H41") == ("H42",)
    assert ("H41", "H42") in matrix.blocking_pairs
    groups = json.loads(matrix.to_json())["compatible_groups"]
    assert all(not {"H41", "H42"} <= set(group) for group in groups)
    assert any("H43" in group for group in groups)


def test_generated_artifact_overlap_blocks_pair() -> None:
    state = HorizonState(
        records=(
            _record("H44", "Events", "management/subprojects/hco/generated.json", OwnedPathMode.GENERATED),
            _record("H45", "CLI", "management/subprojects/hco/generated.json", OwnedPathMode.EXCLUSIVE),
        )
    )

    conflict = build_conflict_matrix(state).conflicts[0]

    assert conflict.kind is ConflictKind.GENERATED_ARTIFACT
    assert conflict.severity is ConflictSeverity.BLOCK
    assert conflict.paths[0].path == "management/subprojects/hco/generated.json"


def test_read_write_overlap_warns_without_blocking() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", "management/subprojects/hco/horizons/**/README.md", OwnedPathMode.READ_ONLY),
            _record("H40", "Doctor", "management/subprojects/hco/horizons/H40/README.md", OwnedPathMode.EXCLUSIVE),
        )
    )

    matrix = build_conflict_matrix(state)

    assert matrix.conflicts[0].kind is ConflictKind.READ_WRITE
    assert matrix.conflicts[0].severity is ConflictSeverity.WARN
    assert matrix.blocking_pairs == ()
    assert matrix.cannot_run_with("H39") == ()


def test_forbidden_path_creates_blocking_policy_conflict() -> None:
    state = HorizonState(
        records=(
            _record("H46", "Preflight", ".mcp.json", OwnedPathMode.EXCLUSIVE),
            _record("H47", "Land", "src/land.py", OwnedPathMode.EXCLUSIVE),
        )
    )

    matrix = build_conflict_matrix(state, forbidden_paths=[".mcp.json"])

    assert len(matrix.conflicts) == 1
    assert matrix.conflicts[0].pair == ("H46", "H46")
    assert matrix.conflicts[0].kind is ConflictKind.FORBIDDEN_FILE
    assert matrix.conflicts[0].severity is ConflictSeverity.BLOCK


def test_dependency_order_is_info_when_paths_do_not_overlap() -> None:
    state = HorizonState(
        records=(
            _record("H39", "State", "src/model.py", OwnedPathMode.EXCLUSIVE),
            _record(
                "H41",
                "Conflict Radar",
                "src/conflicts.py",
                OwnedPathMode.EXCLUSIVE,
                dependencies=(HorizonDependency("H39", "after", "after H39"),),
            ),
        )
    )

    matrix = build_conflict_matrix(state)

    assert matrix.conflicts[0].kind is ConflictKind.DEPENDENCY_ORDER
    assert matrix.conflicts[0].severity is ConflictSeverity.INFO
    assert matrix.blocking_pairs == ()


def test_real_horizon_tree_has_h41_owned_file_conflicts() -> None:
    state = parse_horizon_tree(ROOT / "management/subprojects/hermes-consistency-orchestrator/horizons")

    matrix = build_conflict_matrix(state)
    data = json.loads(matrix.to_json())

    assert data["schema_version"] == 1
    assert data["generated_from"].endswith("management/subprojects/hermes-consistency-orchestrator/horizons")
    assert any(conflict.involves("H41") for conflict in matrix.conflicts)
    assert "H41" in {horizon for group in data["compatible_groups"] for horizon in group}


def _record(
    horizon_id: str,
    title: str,
    path: str,
    mode: OwnedPathMode,
    *,
    wave: int = 7,
    dependencies: tuple[HorizonDependency, ...] = (),
) -> HorizonRecord:
    return HorizonRecord(
        id=horizon_id,
        title=title,
        directory=f"horizons/{horizon_id}",
        source_path=f"horizons/{horizon_id}/README.md",
        wave=wave,
        dependencies=dependencies,
        owned_files=(OwnedPath(path, mode),),
        concurrency="fixture",
    )


if __name__ == "__main__":
    test_write_write_overlap_blocks_pair()
    test_generated_artifact_overlap_blocks_pair()
    test_read_write_overlap_warns_without_blocking()
    test_forbidden_path_creates_blocking_policy_conflict()
    test_dependency_order_is_info_when_paths_do_not_overlap()
    test_real_horizon_tree_has_h41_owned_file_conflicts()
