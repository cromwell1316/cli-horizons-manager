"""Tests for the H40 Horizon Doctor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.doctor import DiagnosticCode, Severity, run_doctor  # noqa: E402
from horizon_manager.model import (  # noqa: E402
    HorizonDependency,
    HorizonRecord,
    HorizonState,
    HorizonStatus,
    OwnedPath,
    OwnedPathMode,
)
from horizon_manager.parser import parse_horizon_tree  # noqa: E402


def test_healthy_fixture_reports_ok_and_stable_json() -> None:
    state = HorizonState(
        (
            _record("H01", status=HorizonStatus.IMPLEMENTED, wave=1),
            _record("H02", status=HorizonStatus.PLANNED, wave=2, deps=("H01",)),
        )
    )
    report = run_doctor(state)
    assert report.ok is True
    assert report.has_errors is False
    assert report.by_code() == {}
    assert report.to_json() == run_doctor(HorizonState(tuple(reversed(state.records)))).to_json()
    data = json.loads(report.to_json())
    assert data["horizon_count"] == 2
    assert data["edge_count"] == 1
    assert data["severity_counts"] == {"error": 0, "warn": 0, "info": 0}


def test_missing_fields_and_malformed_after_refs_have_stable_codes() -> None:
    state = HorizonState(
        (
            HorizonRecord(
                id="H01",
                title="H01",
                directory="horizons/H01",
                source_path="horizons/H01/README.md",
                status=HorizonStatus.UNKNOWN,
                wave=None,
                concurrency="",
                owned_files=(),
                dependencies=(HorizonDependency("H02", "after", "after maybe H02"),),
            ),
            _record("H02"),
        )
    )
    report = run_doctor(state)
    codes = [diagnostic.code for diagnostic in report.diagnostics if str(diagnostic.horizon_id) == "H01"]
    assert codes == [
        DiagnosticCode.MISSING_OWNED_FILES.value,
        DiagnosticCode.MISSING_STATUS.value,
        DiagnosticCode.MISSING_TITLE.value,
        DiagnosticCode.MISSING_WAVE.value,
        DiagnosticCode.MALFORMED_AFTER_REFERENCE.value,
        DiagnosticCode.MISSING_CONCURRENCY.value,
    ]
    assert report.has_errors is True


def test_missing_self_duplicate_refs_and_cycles_are_detected() -> None:
    h01 = _record(
        "H01",
        deps=("H01", "H02", "H02", "H99"),
    )
    h02 = _record("H02", deps=("H03",))
    h03 = _record("H03", deps=("H02",))
    report = run_doctor(HorizonState((h01, h02, h03)))
    by_code = report.by_code()
    assert by_code[DiagnosticCode.SELF_DEPENDENCY.value] == 1
    assert by_code[DiagnosticCode.DUPLICATE_DEPENDENCY.value] == 1
    assert by_code[DiagnosticCode.BAD_DEPENDENCY_REF.value] == 1
    assert by_code[DiagnosticCode.DEPENDENCY_CYCLE.value] == 2
    cycle_messages = [diagnostic.message for diagnostic in report.diagnostics if diagnostic.code == DiagnosticCode.DEPENDENCY_CYCLE.value]
    assert "dependency cycle: H01 -> H01" in cycle_messages
    assert "dependency cycle: H02 -> H03 -> H02" in cycle_messages


def test_evidence_status_mismatches_are_reported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _write(repo / "horizons/H01/V_02_Acceptance_Matrix.md", "| A1 | criterion | cmd | ☐ |\n")
        _write(repo / "horizons/H01/V_03_Implementation_Evidence.md", "Status: planned (Wave 1).\n")
        _write(repo / "horizons/H02/V_02_Acceptance_Matrix.md", "| A1 | criterion | cmd | ☑ |\n| A2 | criterion | cmd | ☑ |\n")
        state = HorizonState(
            (
                _record("H01", status=HorizonStatus.IMPLEMENTED, directory="horizons/H01"),
                _record("H02", status=HorizonStatus.PLANNED, directory="horizons/H02"),
                _record("H03", status=HorizonStatus.IMPLEMENTED, directory="horizons/H03"),
            )
        )
        report = run_doctor(state, repo_root=repo)
    by_code = report.by_code()
    assert by_code[DiagnosticCode.STALE_EVIDENCE_STATUS.value] == 1
    assert by_code[DiagnosticCode.PLANNED_ACCEPTANCE_COMPLETE.value] == 1
    assert by_code[DiagnosticCode.MISSING_EVIDENCE_DOC.value] == 2


def test_generated_artifact_discipline() -> None:
    state = HorizonState(
        (
            _record(
                "H01",
                owned=(
                    OwnedPath("reports/state.json", OwnedPathMode.EXCLUSIVE, "planned generated output reports/state.json", "owned files"),
                    OwnedPath("src/common.py", OwnedPathMode.SHARED, "`src/common.py`", "owned files"),
                ),
            ),
        )
    )
    report = run_doctor(state, generated_paths=("reports/state.json", "reports/missing.json"))
    by_code = report.by_code()
    assert by_code[DiagnosticCode.GENERATED_PATH_NOT_DECLARED.value] == 1
    assert by_code[DiagnosticCode.SHARED_PATH_NEEDS_NOTE.value] == 1
    assert by_code[DiagnosticCode.UNOWNED_GENERATED_FILE.value] == 1


def test_real_horizon_tree_doctor_report_is_deterministic() -> None:
    state = parse_horizon_tree(ROOT / "management/subprojects/hermes-consistency-orchestrator/horizons")
    report = run_doctor(state, repo_root=ROOT)
    assert report.horizon_count >= 54
    assert report.edge_count >= 1
    assert report.to_json() == run_doctor(state, repo_root=ROOT).to_json()
    assert DiagnosticCode.MISSING_CONCURRENCY.value in report.by_code()
    severities = [diagnostic.severity for diagnostic in report.diagnostics]
    assert severities == sorted(severities, key=lambda severity: severity.rank)


def _record(
    horizon_id: str,
    *,
    title: str | None = None,
    status: HorizonStatus = HorizonStatus.PLANNED,
    wave: int | None = 1,
    deps: tuple[str, ...] = (),
    owned: tuple[OwnedPath, ...] | None = None,
    directory: str | None = None,
) -> HorizonRecord:
    directory = directory or f"horizons/{horizon_id}"
    owned = owned if owned is not None else (OwnedPath(f"src/{horizon_id.lower()}.py", OwnedPathMode.EXCLUSIVE, f"`src/{horizon_id.lower()}.py`", "owned files"),)
    return HorizonRecord(
        id=horizon_id,
        title=title or f"{horizon_id} Title",
        directory=directory,
        source_path=f"{directory}/README.md",
        status=status,
        wave=wave,
        concurrency=f"Wave {wave}." if wave else "",
        dependencies=tuple(HorizonDependency(dep, "after", f"after {dep}") for dep in deps),
        owned_files=owned,
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    test_healthy_fixture_reports_ok_and_stable_json()
    test_missing_fields_and_malformed_after_refs_have_stable_codes()
    test_missing_self_duplicate_refs_and_cycles_are_detected()
    test_evidence_status_mismatches_are_reported()
    test_generated_artifact_discipline()
    test_real_horizon_tree_doctor_report_is_deterministic()
