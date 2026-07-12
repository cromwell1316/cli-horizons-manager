"""Start and land preflight checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any, Iterable

from .conflicts import ConflictMatrix, ConflictSeverity
from .doctor import DoctorReport, Severity
from .locks import HorizonLock, LockSnapshot, LockStatus
from .model import HorizonId, HorizonRecord, HorizonState, HorizonStatus, OwnedPath, OwnedPathMode


class PreflightMode(Enum):
    START = "start"
    LAND = "land"

    @classmethod
    def normalize(cls, value: str | "PreflightMode") -> "PreflightMode":
        if isinstance(value, PreflightMode):
            return value
        return cls(str(value).strip().lower())


class CheckStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class CheckSeverity(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass(frozen=True)
class PreflightCheck:
    id: str
    status: CheckStatus | str
    severity: CheckSeverity | str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", str(self.id).strip())
        if isinstance(self.status, str):
            object.__setattr__(self, "status", CheckStatus(self.status))
        if isinstance(self.severity, str):
            object.__setattr__(self, "severity", CheckSeverity(self.severity))
        object.__setattr__(self, "evidence", _stable_value(self.evidence))

    def sort_key(self) -> tuple[int, str]:
        rank = {CheckStatus.FAIL: 0, CheckStatus.WARN: 1, CheckStatus.PASS: 2}[self.status]
        return (rank, self.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class FileScopeResult:
    allowed_paths: tuple[str, ...] = ()
    rejected_paths: tuple[str, ...] = ()
    read_only_paths: tuple[str, ...] = ()
    foreign_owned_paths: tuple[str, ...] = ()
    generated_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "allowed_paths",
            "rejected_paths",
            "read_only_paths",
            "foreign_owned_paths",
            "generated_paths",
            "forbidden_paths",
        ):
            object.__setattr__(self, field_name, tuple(sorted(set(getattr(self, field_name)))))

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "allowed_paths": list(self.allowed_paths),
            "rejected_paths": list(self.rejected_paths),
            "read_only_paths": list(self.read_only_paths),
            "foreign_owned_paths": list(self.foreign_owned_paths),
            "generated_paths": list(self.generated_paths),
            "forbidden_paths": list(self.forbidden_paths),
        }


@dataclass
class PreflightReport:
    horizon_id: HorizonId
    agent_id: str
    mode: PreflightMode
    checks: tuple[PreflightCheck, ...]
    allowed_paths: tuple[str, ...] = ()
    rejected_paths: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        self.horizon_id = HorizonId(self.horizon_id)
        self.agent_id = str(self.agent_id).strip()
        if isinstance(self.mode, str):
            self.mode = PreflightMode.normalize(self.mode)
        self.checks = tuple(sorted(self.checks, key=lambda check: check.sort_key()))
        self.allowed_paths = tuple(sorted(set(self.allowed_paths)))
        self.rejected_paths = tuple(sorted(set(self.rejected_paths)))

    @property
    def ok(self) -> bool:
        return not any(check.status is CheckStatus.FAIL for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "horizon_id": str(self.horizon_id),
            "agent_id": self.agent_id,
            "mode": self.mode.value,
            "ok": self.ok,
            "allowed_paths": list(self.allowed_paths),
            "rejected_paths": list(self.rejected_paths),
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class PreflightContext:
    state: HorizonState
    locks: LockSnapshot | None = None
    doctor_report: DoctorReport | None = None
    conflict_matrix: ConflictMatrix | None = None
    changed_paths: tuple[str, ...] = ()
    now: str | None = None


def run_preflight(
    context: PreflightContext | dict[str, Any],
    horizon_id: str | int,
    agent_id: str,
    mode: PreflightMode | str,
) -> PreflightReport:
    ctx = _coerce_context(context)
    wanted = HorizonId(horizon_id)
    mode_value = PreflightMode.normalize(mode)
    record = ctx.state.get(wanted)
    checks: list[PreflightCheck] = []
    scope = FileScopeResult()

    if record is None:
        checks.append(_fail("horizon.exists", f"{wanted} is not present in horizon state", {"horizon_id": str(wanted)}))
        return PreflightReport(wanted, agent_id, mode_value, tuple(checks))

    checks.append(_pass("horizon.exists", f"{wanted} exists", {"title": record.title}))
    checks.extend(_claim_checks(ctx, record, agent_id))
    checks.extend(_dependency_checks(ctx.state, record, mode_value))
    checks.extend(_doctor_checks(ctx.doctor_report, record))
    checks.extend(_conflict_checks(ctx.conflict_matrix, ctx.locks, record, now=ctx.now))

    if mode_value is PreflightMode.LAND:
        scope = check_file_scope(record.owned_files, ctx.changed_paths, state=ctx.state)
        if scope.rejected_paths:
            checks.append(
                _fail(
                    "files.scope",
                    "changed paths include files outside the horizon write scope",
                    scope.to_dict(),
                )
            )
        else:
            checks.append(_pass("files.scope", "changed paths are within horizon write scope", scope.to_dict()))
    else:
        allowed = tuple(path.path for path in record.owned_files if path.mode is not OwnedPathMode.READ_ONLY)
        scope = FileScopeResult(allowed_paths=allowed)
        checks.append(_pass("files.scope", "start mode records the horizon write scope", scope.to_dict()))

    return PreflightReport(
        horizon_id=record.id,
        agent_id=agent_id,
        mode=mode_value,
        checks=tuple(checks),
        allowed_paths=scope.allowed_paths,
        rejected_paths=scope.rejected_paths,
    )


def check_file_scope(
    owned_paths: Iterable[OwnedPath],
    changed_paths: Iterable[str],
    *,
    state: HorizonState | None = None,
    forbidden_paths: Iterable[str] = (),
) -> FileScopeResult:
    owned = tuple(owned_paths)
    changed = tuple(sorted({_normalize_path(path) for path in changed_paths if str(path).strip()}))
    forbidden = tuple(sorted({_normalize_path(path) for path in forbidden_paths}))
    foreign_owned = _foreign_owned_paths(state, owned) if state is not None else ()

    allowed: list[str] = []
    rejected: list[str] = []
    read_only: list[str] = []
    generated: list[str] = []
    foreign: list[str] = []
    forbidden_hits: list[str] = []

    writable = tuple(path for path in owned if path.mode in {OwnedPathMode.EXCLUSIVE, OwnedPathMode.SHARED, OwnedPathMode.GENERATED, OwnedPathMode.UNKNOWN})
    read_only_decls = tuple(path for path in owned if path.mode is OwnedPathMode.READ_ONLY)
    generated_decls = tuple(path for path in owned if path.mode is OwnedPathMode.GENERATED)

    for path in changed:
        if any(_path_matches(pattern, path) for pattern in forbidden):
            rejected.append(path)
            forbidden_hits.append(path)
            continue
        if any(_path_matches(owned.path, path) for owned in read_only_decls):
            rejected.append(path)
            read_only.append(path)
            continue
        if any(_path_matches(pattern, path) for pattern in foreign_owned):
            rejected.append(path)
            foreign.append(path)
            continue
        if any(_path_matches(owned.path, path) for owned in writable):
            allowed.append(path)
            if any(_path_matches(owned.path, path) for owned in generated_decls):
                generated.append(path)
            continue
        rejected.append(path)
        foreign.append(path)

    return FileScopeResult(
        allowed_paths=tuple(allowed),
        rejected_paths=tuple(rejected),
        read_only_paths=tuple(read_only),
        foreign_owned_paths=tuple(foreign),
        generated_paths=tuple(generated),
        forbidden_paths=tuple(forbidden_hits),
    )


def _claim_checks(ctx: PreflightContext, record: HorizonRecord, agent_id: str) -> list[PreflightCheck]:
    snapshot = ctx.locks or LockSnapshot()
    active = snapshot.active_for_horizon(record.id, now=ctx.now)
    if not active:
        return [_fail("claim.present", f"{record.id} is not actively claimed", {"horizon_id": str(record.id)})]
    owner_matches = [lock for lock in active if lock.agent_id == str(agent_id)]
    if not owner_matches:
        return [
            _fail(
                "claim.owner",
                f"{record.id} is claimed by another agent",
                {"owners": [lock.agent_id for lock in active]},
            )
        ]
    return [_pass("claim.present", f"{record.id} is claimed by {agent_id}", {"lock": owner_matches[0].to_dict()})]


def _dependency_checks(state: HorizonState, record: HorizonRecord, mode: PreflightMode) -> list[PreflightCheck]:
    implemented = {item.id for item in state.records if item.status is HorizonStatus.IMPLEMENTED}
    missing = tuple(sorted((dependency.id for dependency in record.dependencies if dependency.id not in implemented), key=lambda item: item.number))
    if missing:
        return [
            _fail(
                "dependencies.ready",
                f"{record.id} has dependencies that are not implemented",
                {"missing": [str(item) for item in missing], "mode": mode.value},
            )
        ]
    return [_pass("dependencies.ready", f"{record.id} dependencies are implemented", {"mode": mode.value})]


def _doctor_checks(report: DoctorReport | None, record: HorizonRecord) -> list[PreflightCheck]:
    if report is None:
        return [_warn("doctor.available", "doctor report was not supplied", {})]
    diagnostics = [
        diagnostic.to_dict()
        for diagnostic in report.diagnostics
        if diagnostic.horizon_id == record.id and diagnostic.severity is Severity.ERROR
    ]
    if diagnostics:
        return [_fail("doctor.clean", f"{record.id} has doctor error diagnostics", {"diagnostics": diagnostics})]
    return [_pass("doctor.clean", f"{record.id} has no doctor error diagnostics", {})]


def _conflict_checks(
    matrix: ConflictMatrix | None,
    locks: LockSnapshot | None,
    record: HorizonRecord,
    *,
    now: str | None,
) -> list[PreflightCheck]:
    if matrix is None:
        return [_warn("conflicts.clear", "conflict matrix was not supplied", {})]
    active = {
        lock.horizon_id
        for lock in (locks or LockSnapshot()).active_locks
        if lock.horizon_id != record.id and not lock.is_expired(now)
    }
    blockers = []
    for conflict in matrix.blockers_by_horizon.get(record.id, ()):
        if conflict.severity is not ConflictSeverity.BLOCK:
            continue
        other = conflict.other(record.id)
        if other in active:
            blockers.append(conflict.to_dict())
    if blockers:
        return [_fail("conflicts.clear", f"{record.id} conflicts with active claimed horizons", {"conflicts": blockers})]
    return [_pass("conflicts.clear", f"{record.id} has no active blocking conflicts", {})]


def _coerce_context(context: PreflightContext | dict[str, Any]) -> PreflightContext:
    if isinstance(context, PreflightContext):
        return context
    return PreflightContext(
        state=context["state"],
        locks=context.get("locks"),
        doctor_report=context.get("doctor_report") or context.get("doctor"),
        conflict_matrix=context.get("conflict_matrix") or context.get("conflicts"),
        changed_paths=tuple(context.get("changed_paths") or context.get("staged_paths") or ()),
        now=context.get("now"),
    )


def _foreign_owned_paths(state: HorizonState | None, owned_paths: tuple[OwnedPath, ...]) -> tuple[str, ...]:
    if state is None:
        return ()
    own = {path.path for path in owned_paths}
    foreign = []
    for record in state.records:
        for path in record.owned_files:
            if path.path not in own and path.mode is not OwnedPathMode.READ_ONLY:
                foreign.append(path.path)
    return tuple(sorted(set(foreign)))


def _pass(check_id: str, message: str, evidence: dict[str, Any]) -> PreflightCheck:
    return PreflightCheck(check_id, CheckStatus.PASS, CheckSeverity.INFO, message, evidence)


def _warn(check_id: str, message: str, evidence: dict[str, Any]) -> PreflightCheck:
    return PreflightCheck(check_id, CheckStatus.WARN, CheckSeverity.WARN, message, evidence)


def _fail(check_id: str, message: str, evidence: dict[str, Any]) -> PreflightCheck:
    return PreflightCheck(check_id, CheckStatus.FAIL, CheckSeverity.ERROR, message, evidence)


def _normalize_path(path: str) -> str:
    return str(path).strip().replace("\\", "/").strip("/")


def _path_matches(pattern: str, path: str) -> bool:
    pattern = _normalize_path(pattern)
    path = _normalize_path(path)
    if pattern == path:
        return True
    if "**" in pattern:
        prefix = pattern.split("**", 1)[0].rstrip("/")
        return not prefix or path == prefix or path.startswith(prefix + "/")
    if pattern.endswith("/*"):
        prefix = pattern[:-2].rstrip("/")
        return path.startswith(prefix + "/") and "/" not in path[len(prefix) + 1 :]
    if pattern.endswith("*"):
        return path.startswith(pattern[:-1])
    return path.startswith(pattern.rstrip("/") + "/")


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    return value
