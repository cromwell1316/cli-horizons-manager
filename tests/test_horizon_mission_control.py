"""Contract tests for the H54 Mission Control capstone."""

from __future__ import annotations

from pathlib import Path
import tempfile

from horizon_manager.mission_control import (
    CAPSTONE_SEQUENCE,
    REQUIRED_HORIZONS,
    build_capstone_plan,
    render_operator_runbook,
    validate_capstone_readiness,
)


def test_capstone_sequence_is_complete() -> None:
    plan = build_capstone_plan({})

    assert tuple(step.command for step in plan.steps) == CAPSTONE_SEQUENCE
    assert plan.required_horizons == REQUIRED_HORIZONS
    assert any(path.endswith("HORIZON_MISSION_CONTROL.md") for path in plan.generated_artifacts)
    assert plan.to_dict()["commands"] == list(CAPSTONE_SEQUENCE)


def test_capstone_plan_lists_required_artifacts() -> None:
    artifacts = set(build_capstone_plan({}).generated_artifacts)
    for name in (
        "horizon_state.json",
        "horizon_doctor.json",
        "horizon_conflicts.json",
        "horizon_locks.json",
        "horizon_next.json",
        "horizon_preflight.json",
        "horizon_events.jsonl",
        "horizon_dashboard.html",
        "horizon_dependency_graph.html",
        "horizon_snapshots/",
        "HORIZON_MISSION_CONTROL.md",
    ):
        assert any(path.endswith(name) for path in artifacts)


def test_readiness_reports_missing_contracts() -> None:
    plan = build_capstone_plan({})

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        (root / "H39_State").mkdir()
        (root / "H39_State" / "README.md").write_text("# H39\n", encoding="utf-8")
        ok, diagnostics = validate_capstone_readiness(plan, horizons_dir=root)

    assert not ok
    assert "missing horizon contract: H40" in diagnostics
    assert "missing horizon contract: H53" in diagnostics


def test_readiness_reports_missing_required_artifacts() -> None:
    plan = build_capstone_plan({})
    broken = type(plan)(
        steps=plan.steps,
        required_horizons=plan.required_horizons,
        generated_artifacts=tuple(path for path in plan.generated_artifacts if not path.endswith("horizon_dashboard.html")),
    )

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        for horizon in REQUIRED_HORIZONS:
            horizon_dir = root / f"{horizon}_Contract"
            horizon_dir.mkdir()
            (horizon_dir / "README.md").write_text(f"# {horizon}\n", encoding="utf-8")
        ok, diagnostics = validate_capstone_readiness(broken, horizons_dir=root)

    assert not ok
    assert "missing generated artifact: horizon_dashboard.html" in diagnostics


def test_readiness_passes_when_all_contracts_exist() -> None:
    plan = build_capstone_plan({})

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        for horizon in REQUIRED_HORIZONS:
            horizon_dir = root / f"{horizon}_Contract"
            horizon_dir.mkdir()
            (horizon_dir / "README.md").write_text(f"# {horizon}\n", encoding="utf-8")
        ok, diagnostics = validate_capstone_readiness(plan, horizons_dir=root)

    assert ok
    assert diagnostics == ()


def test_runbook_mentions_required_surfaces_and_safety() -> None:
    runbook = render_operator_runbook(build_capstone_plan({}))
    normalized = runbook.casefold()

    for word in ("CLI", "daemon", "watcher", "hooks", "dashboard", "DAG", "time machine"):
        assert word.casefold() in normalized
    assert "do not auto-stage, auto-commit, or auto-push" in runbook
    assert "horizon_snapshots/" in runbook
    assert "Parallel-Agent Rules" in runbook


if __name__ == "__main__":
    test_capstone_sequence_is_complete()
    test_capstone_plan_lists_required_artifacts()
    test_readiness_reports_missing_contracts()
    test_readiness_reports_missing_required_artifacts()
    test_readiness_passes_when_all_contracts_exist()
    test_runbook_mentions_required_surfaces_and_safety()
