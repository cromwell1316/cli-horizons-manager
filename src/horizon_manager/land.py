"""Safe land command support.

H47 is the repository mutation boundary for Horizon Manager. It builds a land plan
from H46 preflight evidence, stages exact allowed paths only, commits with a stable
message, optionally pushes, and records H44 events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Protocol, Sequence

from .events import EventSeverity, EventType, HorizonEvent, append_event
from .model import HorizonId


class LandMode(Enum):
    DRY_RUN = "dry_run"
    COMMIT_ONLY = "commit_only"
    COMMIT_AND_PUSH = "commit_and_push"

    @classmethod
    def normalize(cls, value: str | "LandMode") -> "LandMode":
        if isinstance(value, LandMode):
            return value
        text = str(value).strip().lower().replace("-", "_")
        for mode in cls:
            if mode.value == text:
                return mode
        raise ValueError(f"unknown land mode: {value!r}")


class GitRunner(Protocol):
    def run(self, args: Sequence[str]) -> "GitResult":
        ...


class EventWriter(Protocol):
    def write(self, event: HorizonEvent) -> None:
        ...


@dataclass(frozen=True)
class GitResult:
    args: tuple[str, ...]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "args": list(self.args),
            "ok": self.ok,
            "returncode": self.returncode,
            "stderr": self.stderr,
            "stdout": self.stdout,
        }


@dataclass(frozen=True)
class LandCommand:
    args: tuple[str, ...]
    purpose: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(str(arg) for arg in self.args))
        _reject_broad_staging(self.args)

    def to_dict(self) -> dict[str, object]:
        return {"args": list(self.args), "purpose": self.purpose}


@dataclass(frozen=True)
class LandPlan:
    horizon_id: HorizonId
    agent_id: str
    mode: LandMode
    allowed_files: tuple[str, ...] = ()
    rejected_files: tuple[str, ...] = ()
    commit_message: str = ""
    preflight_report: dict[str, Any] = field(default_factory=dict)
    commands: tuple[LandCommand, ...] = ()
    safe: bool = False
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "agent_id", str(self.agent_id).strip())
        if isinstance(self.mode, str):
            object.__setattr__(self, "mode", LandMode.normalize(self.mode))
        object.__setattr__(self, "allowed_files", tuple(sorted(_normalize_path(path) for path in self.allowed_files)))
        object.__setattr__(self, "rejected_files", tuple(sorted(_normalize_path(path) for path in self.rejected_files)))
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))
        object.__setattr__(self, "preflight_report", _stable_value(self.preflight_report))
        if self.safe and not self.allowed_files:
            object.__setattr__(self, "safe", False)
            object.__setattr__(self, "diagnostics", tuple(sorted((*self.diagnostics, "no_allowed_files"))))
        if self.rejected_files:
            object.__setattr__(self, "safe", False)
        if self.mode is LandMode.DRY_RUN:
            object.__setattr__(self, "commands", ())
        else:
            commands = tuple(self.commands)
            if not all(isinstance(command, LandCommand) for command in commands):
                raise TypeError("LandPlan commands must be LandCommand instances")
            object.__setattr__(self, "commands", commands)

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "allowed_files": list(self.allowed_files),
            "commands": [command.to_dict() for command in self.commands],
            "commit_message": self.commit_message,
            "diagnostics": list(self.diagnostics),
            "horizon_id": str(self.horizon_id),
            "mode": self.mode.value,
            "preflight_report": self.preflight_report,
            "rejected_files": list(self.rejected_files),
            "safe": self.safe,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class LandExecution:
    ok: bool
    plan: LandPlan
    results: tuple[GitResult, ...] = ()
    events: tuple[HorizonEvent, ...] = ()
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "events": [event.to_dict() for event in self.events],
            "message": self.message,
            "ok": self.ok,
            "plan": self.plan.to_dict(),
            "results": [result.to_dict() for result in self.results],
        }


@dataclass(frozen=True)
class SubprocessGitRunner:
    repo_root: Path

    def run(self, args: Sequence[str]) -> GitResult:
        _reject_broad_staging(args)
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        return GitResult(tuple(args), completed.returncode, completed.stdout, completed.stderr)


@dataclass(frozen=True)
class JsonlEventWriter:
    path: Path

    def write(self, event: HorizonEvent) -> None:
        append_event(self.path, event)


PreflightRunner = Callable[[str, str], Any]


def build_land_plan(
    context: Any,
    horizon_id: str | int,
    agent_id: str,
    mode: LandMode | str = LandMode.DRY_RUN,
    *,
    summary: str = "",
    preflight_runner: PreflightRunner | None = None,
) -> LandPlan:
    normalized_mode = LandMode.normalize(mode)
    report = _run_preflight(context, horizon_id, agent_id, preflight_runner)
    data = _report_dict(report)
    ok = bool(data.get("ok", False))
    allowed = tuple(_extract_sequence(data, ("allowed_files", "allowed_paths", "changed_files")))
    rejected = tuple(_extract_sequence(data, ("rejected_files", "rejected_paths", "foreign_files")))
    diagnostics = tuple(str(item) for item in _extract_sequence(data, ("diagnostics", "blockers", "errors")))
    if not ok:
        diagnostics = tuple(sorted((*diagnostics, "preflight_failed")))
    message = commit_message_for(horizon_id, summary or _title_from_report(data))
    commands = _commands_for(normalized_mode, allowed, message)
    return LandPlan(
        horizon_id=HorizonId(horizon_id),
        agent_id=agent_id,
        mode=normalized_mode,
        allowed_files=allowed,
        rejected_files=rejected,
        commit_message=message,
        preflight_report=data,
        commands=commands,
        safe=ok and not rejected,
        diagnostics=diagnostics,
    )


def execute_land_plan(
    plan: LandPlan,
    git_runner: GitRunner,
    event_writer: EventWriter | None = None,
) -> LandExecution:
    if plan.mode is LandMode.DRY_RUN:
        event = _event(plan, EventType.LAND, EventSeverity.INFO, "dry-run land plan", {"mode": plan.mode.value})
        _write_event(event_writer, event)
        return LandExecution(True, plan, events=(event,), message="dry-run only")
    if not plan.safe:
        event = _event(plan, EventType.LAND, EventSeverity.ERROR, "land blocked by preflight", {"diagnostics": list(plan.diagnostics)})
        _write_event(event_writer, event)
        return LandExecution(False, plan, events=(event,), message="preflight failed; no git commands executed")

    results: list[GitResult] = []
    events: list[HorizonEvent] = []
    for command in plan.commands:
        result = git_runner.run(command.args)
        results.append(result)
        if not result.ok:
            event_type = EventType.PUSH if command.args[:1] == ("push",) else EventType.COMMIT
            event = _event(plan, event_type, EventSeverity.ERROR, f"{command.purpose} failed", result.to_dict())
            _write_event(event_writer, event)
            events.append(event)
            return LandExecution(False, plan, tuple(results), tuple(events), f"{command.purpose} failed")
        if command.args[:1] == ("commit",):
            event = _event(plan, EventType.COMMIT, EventSeverity.INFO, "commit completed", result.to_dict())
            _write_event(event_writer, event)
            events.append(event)
        if command.args[:1] == ("push",):
            event = _event(plan, EventType.PUSH, EventSeverity.INFO, "push completed", result.to_dict())
            _write_event(event_writer, event)
            events.append(event)
    return LandExecution(True, plan, tuple(results), tuple(events), "land completed")


def commit_message_for(horizon_id: str | int, summary: str = "") -> str:
    horizon = str(HorizonId(horizon_id))
    text = " ".join(str(summary).strip().split())
    if not text:
        text = "land horizon work"
    if text.lower().startswith(horizon.lower()):
        return text
    return f"{horizon}: {text}"


def _commands_for(mode: LandMode, allowed_files: tuple[str, ...], commit_message: str) -> tuple[LandCommand, ...]:
    if mode is LandMode.DRY_RUN:
        return ()
    commands: list[LandCommand] = []
    for path in sorted({_normalize_path(path) for path in allowed_files}):
        commands.append(LandCommand(("add", "--", path), "stage allowed file"))
    commands.append(LandCommand(("commit", "-m", commit_message), "commit"))
    if mode is LandMode.COMMIT_AND_PUSH:
        commands.append(LandCommand(("push", "origin", "HEAD:master"), "push"))
    return tuple(commands)


def _run_preflight(context: Any, horizon_id: str | int, agent_id: str, runner: PreflightRunner | None) -> Any:
    if runner is not None:
        return runner(str(HorizonId(horizon_id)), str(agent_id))
    candidate = getattr(context, "run_preflight", None)
    if callable(candidate):
        return candidate(str(HorizonId(horizon_id)), str(agent_id))
    return {
        "ok": False,
        "diagnostics": ["preflight_runner_missing"],
        "allowed_files": [],
        "rejected_files": [],
    }


def _report_dict(report: Any) -> dict[str, Any]:
    if isinstance(report, dict):
        return _stable_value(report)
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        return _stable_value(to_dict())
    data = {
        "ok": bool(getattr(report, "ok", False)),
        "allowed_files": tuple(getattr(report, "allowed_files", ())),
        "rejected_files": tuple(getattr(report, "rejected_files", ())),
        "diagnostics": tuple(getattr(report, "diagnostics", ())),
    }
    return _stable_value(data)


def _extract_sequence(data: dict[str, Any], names: tuple[str, ...]) -> tuple[str, ...]:
    for name in names:
        value = data.get(name)
        if isinstance(value, (list, tuple)):
            return tuple(str(item) for item in value)
    return ()


def _event(plan: LandPlan, event_type: EventType, severity: EventSeverity, message: str, detail: dict[str, Any]) -> HorizonEvent:
    return HorizonEvent(
        actor=plan.agent_id,
        horizon_id=plan.horizon_id,
        event_type=event_type,
        severity=severity,
        message=message,
        source="horizon_manager.land",
        detail=detail,
    )


def _write_event(writer: EventWriter | None, event: HorizonEvent) -> None:
    if writer is not None:
        writer.write(event)


def _reject_broad_staging(args: Sequence[str]) -> None:
    parts = tuple(str(arg) for arg in args)
    if not parts:
        return
    if parts[0] == "add" and any(arg in {".", "-A", "--all"} for arg in parts[1:]):
        raise ValueError("broad staging is forbidden")


def _normalize_path(path: str) -> str:
    text = str(path).strip().replace("\\", "/").strip("/")
    if not text or text in {".", "-A", "--all"}:
        raise ValueError(f"unsafe path for land plan: {path!r}")
    return text


def _title_from_report(data: dict[str, Any]) -> str:
    value = data.get("title") or data.get("summary") or "land horizon work"
    return str(value)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
