"""Horizon Manager git hook integration contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from .locks import prune_stale_locks
from .model import HorizonId, HorizonState
from .preflight import PreflightContext, PreflightMode, run_preflight


class HookMode(str, Enum):
    PRE_COMMIT = "pre_commit"
    PRE_PUSH = "pre_push"
    MANUAL = "manual"

    @classmethod
    def normalize(cls, value: str | "HookMode") -> "HookMode":
        if isinstance(value, HookMode):
            return value
        text = str(value).strip().lower().replace("-", "_")
        return cls(text)


class HookChangeClassification(str, Enum):
    HORIZON_OWNED = "horizon-owned"
    INVENTORY = "inventory"
    MANAGER_CODE = "manager-code"
    DETECTOR_OUTPUT = "detector-output"
    GENERATED_OUTPUT = "generated-output"
    UNRELATED = "unrelated"


@dataclass(frozen=True)
class HookContext:
    changed_paths: tuple[Path, ...]
    claimed_horizons: tuple[str, ...] = ()
    agent_id: str = "local-hook"
    state: HorizonState | None = None
    locks: Any | None = None
    doctor_report: Any | None = None
    conflict_matrix: Any | None = None
    now: str | None = None
    readonly: bool = True
    allow_inventory_only: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed_paths", tuple(Path(path) for path in self.changed_paths))
        object.__setattr__(self, "claimed_horizons", tuple(sorted(str(HorizonId(item)) for item in self.claimed_horizons)))


@dataclass(frozen=True)
class HookChange:
    path: str
    status: str
    classification: HookChangeClassification
    horizon_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "classification": self.classification.value,
            "horizon_id": self.horizon_id,
            "path": self.path,
            "status": self.status,
        }


@dataclass(frozen=True)
class HookReport:
    mode: HookMode
    changed_paths: tuple[str, ...]
    horizon_ids: tuple[str, ...]
    changes: tuple[HookChange, ...] = ()
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    bypass_guidance: str = ""
    ok: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", HookMode.normalize(self.mode))
        object.__setattr__(self, "changed_paths", tuple(sorted(str(path) for path in self.changed_paths)))
        object.__setattr__(self, "horizon_ids", tuple(sorted(str(HorizonId(item)) for item in self.horizon_ids)))
        object.__setattr__(self, "changes", tuple(sorted(self.changes, key=lambda item: item.path)))
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "bypass_guidance": self.bypass_guidance,
            "changed_paths": list(self.changed_paths),
            "changes": [change.to_dict() for change in self.changes],
            "diagnostics": list(self.diagnostics),
            "horizon_ids": list(self.horizon_ids),
            "mode": self.mode.value,
            "ok": self.ok,
        }


def classify_hook_change(path: str | Path) -> str:
    return _classify_hook_change(path).value


def run_hook(mode: HookMode | str, context: HookContext) -> HookReport:
    hook_mode = HookMode.normalize(mode)
    changes = tuple(_hook_change(path, context) for path in context.changed_paths)
    horizon_ids = tuple(sorted({change.horizon_id for change in changes if change.horizon_id}))
    diagnostics = _diagnostics(hook_mode, context, changes, horizon_ids)
    diagnostics.extend(_preflight_diagnostics(context, horizon_ids, _effective_claimed_horizons(context)))
    if _inventory_only(changes) and context.allow_inventory_only:
        diagnostics = [item for item in diagnostics if not item.startswith(("stale inventory:", "unrelated paths"))]

    ok = not diagnostics
    guidance = ""
    if not ok:
        guidance = (
            "Next action: run `horizon-manager preflight`, claim the affected horizon, "
            "or bypass explicitly with git --no-verify according to local policy."
        )
    return HookReport(
        mode=hook_mode,
        changed_paths=tuple(change.path for change in changes),
        horizon_ids=horizon_ids,
        changes=changes,
        diagnostics=tuple(diagnostics),
        bypass_guidance=guidance,
        ok=ok,
    )


def render_hook_report(report: HookReport, format: str = "text") -> str:
    if format == "json":
        return json.dumps(report.to_dict(), sort_keys=True)
    lines = [f"horizon hook {report.mode.value}: {'ok' if report.ok else 'blocked'}"]
    for change in report.changes:
        suffix = f" ({change.horizon_id})" if change.horizon_id else ""
        lines.append(f"- {change.classification.value}: {change.path}{suffix}")
    for diagnostic in report.diagnostics:
        lines.append(f"! {diagnostic}")
    if report.bypass_guidance:
        lines.append(report.bypass_guidance)
    return "\n".join(lines)


def changed_paths_from_strings(paths: Iterable[str]) -> tuple[Path, ...]:
    return tuple(Path(path) for path in paths)


def collect_git_changed_paths(mode: HookMode | str, repo_root: str | Path = ".") -> tuple[Path, ...]:
    hook_mode = HookMode.normalize(mode)
    root = Path(repo_root)
    if hook_mode is HookMode.PRE_COMMIT:
        args = ("diff", "--cached", "--name-only", "--diff-filter=ACMRT")
    elif hook_mode is HookMode.PRE_PUSH:
        args = ("diff", "--name-only", "--diff-filter=ACMRT", "@{upstream}...HEAD")
    else:
        args = ("diff", "--name-only", "--diff-filter=ACMRT")
    result = subprocess.run(("git", *args), cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0 and hook_mode is HookMode.PRE_PUSH:
        result = subprocess.run(
            ("git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD~1...HEAD"),
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    if result.returncode != 0:
        return ()
    return tuple(Path(line.strip()) for line in result.stdout.splitlines() if line.strip())


_HORIZON_DIR_NAMES = frozenset({"horizons", "horizonts"})


def _classify_hook_change(path: str | Path) -> HookChangeClassification:
    text = str(path).replace("\\", "/")
    name = Path(text).name
    if _has_horizon_dir_segment(text):
        return HookChangeClassification.HORIZON_OWNED
    if name == "MANAGEMENT_DOC_INVENTORY.md":
        return HookChangeClassification.INVENTORY
    if text.endswith(".json") and "management/subprojects/hermes-consistency-orchestrator/horizon_" in text:
        return HookChangeClassification.GENERATED_OUTPUT
    if text.endswith(".html") and "management/subprojects/hermes-consistency-orchestrator/horizon_" in text:
        return HookChangeClassification.GENERATED_OUTPUT
    if "horizon-manager/" in text:
        return HookChangeClassification.MANAGER_CODE
    if text.startswith("deep_audit/") or "/deep_audit/" in text:
        return HookChangeClassification.DETECTOR_OUTPUT
    return HookChangeClassification.UNRELATED


def _extract_horizon_id(path: Path) -> str | None:
    parts = path.as_posix().split("/")
    index = next((idx for idx, part in enumerate(parts) if part in _HORIZON_DIR_NAMES), None)
    if index is None:
        return None
    if index + 1 >= len(parts):
        return None
    candidate = parts[index + 1].split("_", 1)[0]
    return candidate if candidate.startswith("H") and candidate[1:].isdigit() else None


def _has_horizon_dir_segment(path: str) -> bool:
    return any(part in _HORIZON_DIR_NAMES for part in path.split("/"))


def _hook_change(path: Path, context: HookContext) -> HookChange:
    normalized = path.as_posix()
    horizon_id = _extract_horizon_id(path) or _state_owner_for(context.state, normalized)
    return HookChange(
        path=normalized,
        status="changed",
        classification=_classify_hook_change(path),
        horizon_id=horizon_id,
    )


def _diagnostics(
    mode: HookMode,
    context: HookContext,
    changes: tuple[HookChange, ...],
    horizon_ids: tuple[str, ...],
) -> list[str]:
    diagnostics: list[str] = []
    claimed = set(_effective_claimed_horizons(context))
    classifications = {change.classification for change in changes}

    if HookChangeClassification.DETECTOR_OUTPUT in classifications:
        diagnostics.append("deep-audit detector output is outside hook mutation scope")
    unclaimed = [horizon_id for horizon_id in horizon_ids if horizon_id not in claimed]
    if unclaimed:
        diagnostics.append("unclaimed horizon edits: " + ", ".join(unclaimed))
    foreign_paths = tuple(
        change.path
        for change in changes
        if change.horizon_id and change.horizon_id not in claimed and change.classification is not HookChangeClassification.HORIZON_OWNED
    )
    if foreign_paths:
        diagnostics.append("foreign owned-file changes: " + ", ".join(foreign_paths))
    if HookChangeClassification.INVENTORY in classifications and not _inventory_only(changes):
        diagnostics.append("stale inventory: inventory churn must be regenerated after horizon edits")
    if HookChangeClassification.UNRELATED in classifications and mode is not HookMode.MANUAL:
        diagnostics.append("unrelated paths require explicit manual review")
    return diagnostics


def _preflight_diagnostics(context: HookContext, horizon_ids: tuple[str, ...], claimed_horizons: tuple[str, ...]) -> list[str]:
    if context.state is None:
        return []
    diagnostics: list[str] = []
    for horizon_id in horizon_ids:
        if horizon_id not in claimed_horizons:
            continue
        report = run_preflight(
            PreflightContext(
                state=context.state,
                locks=context.locks,
                doctor_report=context.doctor_report,
                conflict_matrix=context.conflict_matrix,
                changed_paths=tuple(path.as_posix() for path in context.changed_paths),
                now=context.now,
            ),
            horizon_id,
            context.agent_id,
            PreflightMode.LAND,
        )
        if not report.ok:
            failed = ", ".join(check.id for check in report.checks if check.status.value == "fail")
            diagnostics.append(f"preflight failed for {horizon_id}: {failed}")
    return diagnostics


def _effective_claimed_horizons(context: HookContext) -> tuple[str, ...]:
    claims = {str(HorizonId(item)) for item in context.claimed_horizons}
    if context.locks is None:
        return tuple(sorted(claims, key=lambda item: HorizonId(item).number))
    snapshot = prune_stale_locks(context.locks, now=context.now)
    for lock in snapshot.active_locks:
        if lock.agent_id == context.agent_id and not lock.is_expired(context.now):
            claims.add(str(lock.horizon_id))
    return tuple(sorted(claims, key=lambda item: HorizonId(item).number))


def _inventory_only(changes: tuple[HookChange, ...]) -> bool:
    return bool(changes) and {change.classification for change in changes} == {HookChangeClassification.INVENTORY}


def _state_owner_for(state: HorizonState | None, path: str) -> str | None:
    if state is None:
        return None
    candidates: list[str] = []
    for record in state.records:
        for owned in record.owned_files:
            if _path_matches(owned.path, path):
                candidates.append(str(record.id))
    return sorted(candidates, key=lambda item: HorizonId(item).number)[0] if candidates else None


def _path_matches(pattern: str, path: str) -> bool:
    pattern = str(pattern).strip().replace("\\", "/").strip("/")
    path = str(path).strip().replace("\\", "/").strip("/")
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
