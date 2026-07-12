"""Horizon health diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .model import HorizonId, HorizonRecord, HorizonState, HorizonStatus, OwnedPathMode


class Severity(Enum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {Severity.ERROR: 0, Severity.WARN: 1, Severity.INFO: 2}[self]

    @classmethod
    def normalize(cls, value: str | "Severity") -> "Severity":
        if isinstance(value, Severity):
            return value
        return cls(str(value).lower())


class DiagnosticCode(str, Enum):
    MISSING_STATUS = "missing_status"
    UNKNOWN_STATUS = "unknown_status"
    MISSING_TITLE = "missing_title"
    MISSING_WAVE = "missing_wave"
    MISSING_CONCURRENCY = "missing_concurrency"
    MISSING_OWNED_FILES = "missing_owned_files"
    BAD_DEPENDENCY_REF = "bad_dependency_ref"
    SELF_DEPENDENCY = "self_dependency"
    DUPLICATE_DEPENDENCY = "duplicate_dependency"
    DEPENDENCY_CYCLE = "dependency_cycle"
    MALFORMED_AFTER_REFERENCE = "malformed_after_reference"
    STALE_EVIDENCE_STATUS = "stale_evidence_status"
    MISSING_EVIDENCE_DOC = "missing_evidence_doc"
    PLANNED_ACCEPTANCE_COMPLETE = "planned_acceptance_complete"
    UNOWNED_GENERATED_FILE = "unowned_generated_file"
    GENERATED_PATH_NOT_DECLARED = "generated_path_not_declared"
    SHARED_PATH_NEEDS_NOTE = "shared_path_needs_note"
    PARSE_WARNING = "parse_warning"


@dataclass(frozen=True)
class Diagnostic:
    code: str | DiagnosticCode
    severity: Severity | str
    horizon_id: HorizonId | str | None
    message: str
    source_path: str = ""
    section: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = self.code.value if isinstance(self.code, DiagnosticCode) else str(self.code)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "severity", Severity.normalize(self.severity))
        if self.horizon_id is not None:
            object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "evidence", _stable_value(self.evidence))

    def sort_key(self) -> tuple[int, int, str, str, str, str]:
        horizon_number = self.horizon_id.number if self.horizon_id else 0
        return (self.severity.rank, horizon_number, self.code, self.source_path, self.section, self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "horizon_id": str(self.horizon_id) if self.horizon_id else None,
            "message": self.message,
            "source_path": self.source_path,
            "section": self.section,
            "evidence": self.evidence,
        }


@dataclass
class DoctorReport:
    diagnostics: tuple[Diagnostic, ...]
    horizon_count: int
    edge_count: int

    def __post_init__(self) -> None:
        self.diagnostics = tuple(sorted(self.diagnostics, key=lambda diagnostic: diagnostic.sort_key()))

    @property
    def has_errors(self) -> bool:
        return any(diagnostic.severity is Severity.ERROR for diagnostic in self.diagnostics)

    @property
    def ok(self) -> bool:
        return not self.has_errors

    def by_horizon(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for diagnostic in self.diagnostics:
            grouped[str(diagnostic.horizon_id) if diagnostic.horizon_id else "global"].append(diagnostic.to_dict())
        return {key: grouped[key] for key in sorted(grouped, key=_horizon_group_key)}

    def by_code(self) -> dict[str, int]:
        counts = Counter(diagnostic.code for diagnostic in self.diagnostics)
        return {code: counts[code] for code in sorted(counts)}

    def severity_counts(self) -> dict[str, int]:
        counts = Counter(diagnostic.severity.value for diagnostic in self.diagnostics)
        return {severity.value: counts.get(severity.value, 0) for severity in Severity}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "has_errors": self.has_errors,
            "horizon_count": self.horizon_count,
            "edge_count": self.edge_count,
            "diagnostic_count": len(self.diagnostics),
            "severity_counts": self.severity_counts(),
            "by_code": self.by_code(),
            "by_horizon": self.by_horizon(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run_doctor(
    state: HorizonState,
    *,
    repo_root: str | Path | None = None,
    check_source_exists: bool = False,
    generated_paths: Iterable[str] = (),
) -> DoctorReport:
    diagnostics: list[Diagnostic] = []
    records = tuple(state.records)
    by_id = {str(record.id): record for record in records}

    for record in records:
        diagnostics.extend(_metadata_diagnostics(record))
        diagnostics.extend(_parse_warning_diagnostics(record))
        diagnostics.extend(_dependency_diagnostics(record, by_id))
        diagnostics.extend(_ownership_diagnostics(record))
        if repo_root is not None:
            diagnostics.extend(_evidence_diagnostics(record, Path(repo_root), check_source_exists))

    diagnostics.extend(_cycle_diagnostics(records))
    diagnostics.extend(_generated_artifact_diagnostics(records, generated_paths))

    return DoctorReport(
        diagnostics=tuple(_dedupe_diagnostics(diagnostics)),
        horizon_count=len(records),
        edge_count=len(state.dependency_edges()),
    )


def _metadata_diagnostics(record: HorizonRecord) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not str(record.title).strip() or record.title == str(record.id):
        diagnostics.append(_diagnostic(DiagnosticCode.MISSING_TITLE, Severity.ERROR, record, "missing horizon title", section="metadata"))
    if record.status is HorizonStatus.UNKNOWN:
        diagnostics.append(_diagnostic(DiagnosticCode.MISSING_STATUS, Severity.ERROR, record, "missing or unknown status", section="metadata"))
    if record.wave is None:
        diagnostics.append(_diagnostic(DiagnosticCode.MISSING_WAVE, Severity.ERROR, record, "missing Wave marker", section="metadata"))
    if not record.concurrency.strip():
        diagnostics.append(_diagnostic(DiagnosticCode.MISSING_CONCURRENCY, Severity.WARN, record, "missing Concurrency section", section="Concurrency"))
    writable = [owned for owned in record.owned_files if owned.mode is not OwnedPathMode.READ_ONLY]
    if not writable:
        diagnostics.append(_diagnostic(DiagnosticCode.MISSING_OWNED_FILES, Severity.ERROR, record, "missing writable Owned Files declaration", section="Owned Files"))
    return diagnostics


def _parse_warning_diagnostics(record: HorizonRecord) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    direct_codes = {
        DiagnosticCode.MISSING_STATUS.value,
        DiagnosticCode.UNKNOWN_STATUS.value,
        DiagnosticCode.MISSING_WAVE.value,
        DiagnosticCode.MISSING_CONCURRENCY.value,
        DiagnosticCode.MISSING_OWNED_FILES.value,
    }
    for warning in record.warnings:
        if warning.code in direct_codes:
            continue
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.PARSE_WARNING,
                severity=Severity.WARN,
                horizon_id=record.id,
                message=warning.message,
                source_path=warning.source_path or record.source_path,
                section=warning.section,
                evidence={"parser_code": warning.code},
            )
        )
    return diagnostics


def _dependency_diagnostics(record: HorizonRecord, by_id: dict[str, HorizonRecord]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: set[str] = set()
    for dependency in record.dependencies:
        dep_id = str(dependency.id)
        if dep_id == str(record.id):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.SELF_DEPENDENCY,
                    Severity.ERROR,
                    record,
                    f"{record.id} depends on itself",
                    section=dependency.source,
                    evidence=dependency.to_dict(),
                )
            )
        if dep_id not in by_id:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.BAD_DEPENDENCY_REF,
                    Severity.ERROR,
                    record,
                    f"dependency {dep_id} is not present in horizon state",
                    section=dependency.source,
                    evidence=dependency.to_dict(),
                )
            )
        if dep_id in seen:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.DUPLICATE_DEPENDENCY,
                    Severity.WARN,
                    record,
                    f"dependency {dep_id} is declared more than once",
                    section=dependency.source,
                    evidence=dependency.to_dict(),
                )
            )
        seen.add(dep_id)
        if dependency.source == "after" and not _after_ref_looks_well_formed(dependency.raw):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.MALFORMED_AFTER_REFERENCE,
                    Severity.WARN,
                    record,
                    f"after dependency on {dep_id} came from a malformed reference",
                    section=dependency.source,
                    evidence=dependency.to_dict(),
                )
            )
    return diagnostics


def _cycle_diagnostics(records: tuple[HorizonRecord, ...]) -> list[Diagnostic]:
    graph = {str(record.id): sorted({str(dependency.id) for dependency in record.dependencies}) for record in records}
    known = set(graph)
    graph = {node: [dep for dep in deps if dep in known] for node, deps in graph.items()}
    cycles = _find_cycles(graph)
    diagnostics: list[Diagnostic] = []
    for cycle in cycles:
        record = next(record for record in records if str(record.id) == cycle[0])
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DEPENDENCY_CYCLE,
                Severity.ERROR,
                record,
                "dependency cycle: " + " -> ".join(cycle),
                section="dependencies",
                evidence={"cycle": cycle},
            )
        )
    return diagnostics


def _ownership_diagnostics(record: HorizonRecord) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for owned in record.owned_files:
        lower = owned.path.lower()
        if lower.endswith((".json", ".jsonl", ".html")) and "generated" in owned.raw.lower() and owned.mode is not OwnedPathMode.GENERATED:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.GENERATED_PATH_NOT_DECLARED,
                    Severity.WARN,
                    record,
                    f"generated artifact {owned.path} is not marked generated",
                    section=owned.section,
                    evidence=owned.to_dict(),
                )
            )
        if owned.mode is OwnedPathMode.SHARED and not _has_shared_note(owned.raw):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.SHARED_PATH_NEEDS_NOTE,
                    Severity.WARN,
                    record,
                    f"shared path {owned.path} needs a coordination note",
                    section=owned.section,
                    evidence=owned.to_dict(),
                )
            )
    return diagnostics


def _generated_artifact_diagnostics(records: tuple[HorizonRecord, ...], generated_paths: Iterable[str]) -> list[Diagnostic]:
    declared = {
        owned.path
        for record in records
        for owned in record.owned_files
        if owned.mode in {OwnedPathMode.GENERATED, OwnedPathMode.EXCLUSIVE, OwnedPathMode.SHARED}
    }
    diagnostics: list[Diagnostic] = []
    for path in sorted(set(generated_paths)):
        if path not in declared:
            diagnostics.append(
                Diagnostic(
                    code=DiagnosticCode.UNOWNED_GENERATED_FILE,
                    severity=Severity.ERROR,
                    horizon_id=None,
                    message=f"generated artifact {path} is not declared by any horizon",
                    section="generated_artifacts",
                    evidence={"path": path},
                )
            )
    return diagnostics


def _evidence_diagnostics(record: HorizonRecord, repo_root: Path, check_source_exists: bool) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    directory = repo_root / record.directory
    if check_source_exists and not (repo_root / record.source_path).exists():
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.STALE_EVIDENCE_STATUS,
                Severity.ERROR,
                record,
                "source README path does not exist",
                section="source_path",
                evidence={"source_path": record.source_path},
            )
        )
    v02 = directory / "V_02_Acceptance_Matrix.md"
    v03 = directory / "V_03_Implementation_Evidence.md"
    if record.status is HorizonStatus.IMPLEMENTED:
        for path in (v02, v03):
            if not path.exists():
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.MISSING_EVIDENCE_DOC,
                        Severity.ERROR,
                        record,
                        f"implemented horizon is missing {path.name}",
                        section="evidence",
                        evidence={"path": _display_path(path, repo_root)},
                    )
                )
        if v03.exists():
            text = v03.read_text(encoding="utf-8")
            if "Status: planned" in text:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.STALE_EVIDENCE_STATUS,
                        Severity.ERROR,
                        record,
                        "implemented horizon evidence still says planned",
                        section="V_03",
                        evidence={"path": _display_path(v03, repo_root)},
                    )
                )
    if record.status is HorizonStatus.PLANNED and v02.exists():
        text = v02.read_text(encoding="utf-8")
        if _all_acceptance_rows_done(text):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.PLANNED_ACCEPTANCE_COMPLETE,
                    Severity.WARN,
                    record,
                    "planned horizon claims all acceptance rows complete",
                    section="V_02",
                    evidence={"path": _display_path(v02, repo_root)},
                )
            )
    return diagnostics


def _all_acceptance_rows_done(text: str) -> bool:
    rows = [line for line in text.splitlines() if line.startswith("| A")]
    if not rows:
        return False
    return all("☑" in row or "[x]" in row.lower() for row in rows)


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            idx = stack.index(node)
            cycle = stack[idx:] + [node]
            cycles.add(_canonical_cycle(cycle))
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for dep in graph.get(node, []):
            visit(dep)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph, key=lambda item: HorizonId(item).number):
        visit(node)
    return [list(cycle) for cycle in sorted(cycles, key=lambda item: (len(item), item))]


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    body = cycle[:-1]
    rotations = [body[idx:] + body[:idx] for idx in range(len(body))]
    best = min(rotations, key=lambda item: [HorizonId(value).number for value in item])
    return tuple(best + [best[0]])


def _dedupe_diagnostics(diagnostics: Iterable[Diagnostic]) -> list[Diagnostic]:
    by_key: dict[tuple[Any, ...], Diagnostic] = {}
    for diagnostic in diagnostics:
        key = (
            diagnostic.code,
            diagnostic.severity.value,
            str(diagnostic.horizon_id) if diagnostic.horizon_id else None,
            diagnostic.message,
            diagnostic.source_path,
            diagnostic.section,
            json.dumps(diagnostic.evidence, ensure_ascii=False, sort_keys=True),
        )
        by_key.setdefault(key, diagnostic)
    return sorted(by_key.values(), key=lambda diagnostic: diagnostic.sort_key())


def _diagnostic(
    code: DiagnosticCode,
    severity: Severity,
    record: HorizonRecord,
    message: str,
    *,
    section: str,
    evidence: dict[str, Any] | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        horizon_id=record.id,
        message=message,
        source_path=record.source_path,
        section=section,
        evidence=evidence or {},
    )


def _after_ref_looks_well_formed(raw: str) -> bool:
    return bool(re.search(r"\bafter\s+(?:HCO-)?H\d{1,3}", raw, re.IGNORECASE))


def _has_shared_note(raw: str) -> bool:
    lowered = raw.lower()
    return any(token in lowered for token in ("coordinate", "shared", "parallel", "note"))


def _horizon_group_key(value: str) -> tuple[int, str]:
    if value == "global":
        return (0, value)
    return (HorizonId(value).number, value)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    return value
