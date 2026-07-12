"""Tests for the H46 Horizon Preflight Gate."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.conflicts import Conflict, ConflictKind, ConflictMatrix, ConflictPath, ConflictSeverity  # noqa: E402
from horizon_manager.doctor import Diagnostic, DoctorReport, Severity  # noqa: E402
from horizon_manager.locks import HorizonLock, LockSnapshot, LockStatus  # noqa: E402
from horizon_manager.model import HorizonDependency, HorizonRecord, HorizonState, HorizonStatus, OwnedPath, OwnedPathMode  # noqa: E402
from horizon_manager.preflight import PreflightContext, PreflightMode, check_file_scope, run_preflight  # noqa: E402


NOW = "2026-07-11T12:00:00Z"
LATER = "2026-07-11T13:00:00Z"
EARLIER = "2026-07-11T11:00:00Z"


def test_start_mode_passes_with_current_claim_and_stable_json() -> None:
    ctx = _context(locks=_locks(_lock("H46", "agent-a")))
    report = run_preflight(ctx, "h46", "agent-a", PreflightMode.START)
    assert report.ok is True
    assert report.allowed_paths == ("management/subprojects/horizon-manager/src/horizon_manager/preflight.py",)
    assert report.to_json() == run_preflight(ctx, "H46", "agent-a", "start").to_json()
    assert [check["id"] for check in report.to_dict()["checks"]] == [
        "claim.present",
        "conflicts.clear",
        "dependencies.ready",
        "doctor.clean",
        "files.scope",
        "horizon.exists",
    ]


def test_missing_and_stale_claims_fail() -> None:
    missing = run_preflight(_context(locks=LockSnapshot()), "H46", "agent-a", "start")
    assert missing.ok is False
    assert _codes(missing) == ["claim.present"]

    stale = run_preflight(
        _context(locks=_locks(_lock("H46", "agent-a", expires_at=EARLIER))),
        "H46",
        "agent-a",
        "start",
    )
    assert stale.ok is False
    assert _codes(stale) == ["claim.present"]

    owner = run_preflight(_context(locks=_locks(_lock("H46", "agent-b"))), "H46", "agent-a", "start")
    assert owner.ok is False
    assert _codes(owner) == ["claim.owner"]


def test_land_mode_rejects_foreign_read_only_and_forbidden_files() -> None:
    ctx = _context(
        locks=_locks(_lock("H46", "agent-a")),
        changed_paths=(
            "management/subprojects/horizon-manager/src/horizon_manager/preflight.py",
            "management/subprojects/horizon-manager/src/horizon_manager/locks.py",
            "management/subprojects/hermes-consistency-orchestrator/horizons/H40_Horizon_Doctor/README.md",
            "secrets/token.txt",
        ),
    )
    scope = check_file_scope(
        ctx.state.require("H46").owned_files,
        ctx.changed_paths,
        state=ctx.state,
        forbidden_paths=("secrets/**",),
    )
    assert scope.allowed_paths == ("management/subprojects/horizon-manager/src/horizon_manager/preflight.py",)
    assert "management/subprojects/horizon-manager/src/horizon_manager/locks.py" in scope.foreign_owned_paths
    assert "management/subprojects/hermes-consistency-orchestrator/horizons/H40_Horizon_Doctor/README.md" in scope.read_only_paths
    assert "secrets/token.txt" in scope.forbidden_paths

    report = run_preflight(ctx, "H46", "agent-a", "land")
    assert report.ok is False
    assert _codes(report) == ["files.scope"]


def test_doctor_and_conflict_blockers_fail() -> None:
    doctor = DoctorReport(
        diagnostics=(
            Diagnostic(
                code="missing_owned_files",
                severity=Severity.ERROR,
                horizon_id="H46",
                message="bad H46",
                source_path="README.md",
                section="Owned Files",
            ),
        ),
        horizon_count=2,
        edge_count=1,
    )
    doctor_report = run_preflight(_context(locks=_locks(_lock("H46", "agent-a")), doctor_report=doctor), "H46", "agent-a", "start")
    assert doctor_report.ok is False
    assert _codes(doctor_report) == ["doctor.clean"]

    matrix = ConflictMatrix(
        (
            Conflict(
                "H46",
                "H42",
                ConflictKind.WRITE_WRITE,
                ConflictSeverity.BLOCK,
                (ConflictPath("management/subprojects/horizon-manager/src/horizon_manager/preflight.py", OwnedPathMode.EXCLUSIVE, OwnedPathMode.EXCLUSIVE),),
                "collision",
            ),
        )
    )
    conflict_report = run_preflight(
        _context(locks=_locks(_lock("H46", "agent-a"), _lock("H42", "agent-b")), conflict_matrix=matrix),
        "H46",
        "agent-a",
        "start",
    )
    assert conflict_report.ok is False
    assert _codes(conflict_report) == ["conflicts.clear"]


def test_dependencies_block_when_not_implemented() -> None:
    state = _state(h42_status=HorizonStatus.PLANNED)
    report = run_preflight(_context(state=state, locks=_locks(_lock("H46", "agent-a"))), "H46", "agent-a", "start")
    assert report.ok is False
    assert _codes(report) == ["dependencies.ready"]


def test_land_mode_passes_with_owned_changed_files() -> None:
    ctx = _context(
        locks=_locks(_lock("H46", "agent-a")),
        changed_paths=("management/subprojects/horizon-manager/src/horizon_manager/preflight.py",),
    )
    report = run_preflight(ctx, "H46", "agent-a", "land")
    assert report.ok is True
    assert report.allowed_paths == ("management/subprojects/horizon-manager/src/horizon_manager/preflight.py",)
    assert report.rejected_paths == ()


def _context(
    *,
    state: HorizonState | None = None,
    locks: LockSnapshot | None = None,
    doctor_report: DoctorReport | None = None,
    conflict_matrix: ConflictMatrix | None = None,
    changed_paths: tuple[str, ...] = (),
) -> PreflightContext:
    return PreflightContext(
        state=state or _state(),
        locks=locks or LockSnapshot(),
        doctor_report=doctor_report or DoctorReport((), horizon_count=2, edge_count=1),
        conflict_matrix=conflict_matrix or ConflictMatrix(()),
        changed_paths=changed_paths,
        now=NOW,
    )


def _state(*, h42_status: HorizonStatus = HorizonStatus.IMPLEMENTED) -> HorizonState:
    h42 = HorizonRecord(
        id="H42",
        title="Horizon Locks",
        directory="horizons/H42",
        source_path="horizons/H42/README.md",
        status=h42_status,
        wave=9,
        concurrency="Wave 9.",
        owned_files=(OwnedPath("management/subprojects/horizon-manager/src/horizon_manager/locks.py", OwnedPathMode.EXCLUSIVE, "", "owned files"),),
    )
    h46 = HorizonRecord(
        id="H46",
        title="Horizon Preflight Gate",
        directory="horizons/H46",
        source_path="horizons/H46/README.md",
        status=HorizonStatus.PLANNED,
        wave=9,
        concurrency="Wave 9 after H42.",
        dependencies=(HorizonDependency("H42", "after", "after H42"),),
        owned_files=(
            OwnedPath("management/subprojects/horizon-manager/src/horizon_manager/preflight.py", OwnedPathMode.EXCLUSIVE, "", "owned files"),
            OwnedPath("management/subprojects/hermes-consistency-orchestrator/horizons/**/README.md", OwnedPathMode.READ_ONLY, "", "consumed contracts"),
        ),
    )
    return HorizonState((h42, h46))


def _locks(*locks: HorizonLock) -> LockSnapshot:
    return LockSnapshot(locks=locks, generated_at=NOW)


def _lock(horizon_id: str, agent_id: str, *, expires_at: str = LATER) -> HorizonLock:
    return HorizonLock(
        horizon_id=horizon_id,
        agent_id=agent_id,
        status=LockStatus.ACTIVE,
        claimed_paths=(),
        claimed_at=NOW,
        expires_at=expires_at,
        ttl_seconds=3600,
    )


def _codes(report) -> list[str]:
    return [check.id for check in report.checks if check.status.value == "fail"]


if __name__ == "__main__":
    test_start_mode_passes_with_current_claim_and_stable_json()
    test_missing_and_stale_claims_fail()
    test_land_mode_rejects_foreign_read_only_and_forbidden_files()
    test_doctor_and_conflict_blockers_fail()
    test_dependencies_block_when_not_implemented()
    test_land_mode_passes_with_owned_changed_files()
