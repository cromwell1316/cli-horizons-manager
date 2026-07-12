"""Horizon lifecycle event log."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator
from uuid import uuid4

from .model import HorizonId


SCHEMA_VERSION = 1


class EventType(Enum):
    CLAIM = "claim"
    RELEASE = "release"
    DOCTOR = "doctor"
    PREFLIGHT = "preflight"
    LAND = "land"
    COMMIT = "commit"
    PUSH = "push"
    RENDER = "render"
    DAEMON = "daemon"
    HOOK = "hook"
    NOTE = "note"

    @classmethod
    def normalize(cls, value: str | "EventType") -> "EventType":
        if isinstance(value, EventType):
            return value
        return cls(str(value).strip().lower())


class EventSeverity(Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"

    @classmethod
    def normalize(cls, value: str | "EventSeverity") -> "EventSeverity":
        if isinstance(value, EventSeverity):
            return value
        return cls(str(value).strip().lower())


@dataclass(frozen=True)
class HorizonEvent:
    schema_version: int = SCHEMA_VERSION
    event_id: str = field(default_factory=lambda: uuid4().hex)
    ts: str = field(default_factory=lambda: _utc_now())
    actor: str = ""
    horizon_id: HorizonId | str | None = None
    event_type: EventType | str = EventType.NOTE
    severity: EventSeverity | str = EventSeverity.INFO
    message: str = ""
    correlation_id: str = ""
    source: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", str(self.event_id).strip())
        object.__setattr__(self, "ts", _normalize_ts(self.ts))
        object.__setattr__(self, "actor", str(self.actor).strip())
        if self.horizon_id is not None:
            object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "event_type", EventType.normalize(self.event_type))
        object.__setattr__(self, "severity", EventSeverity.normalize(self.severity))
        object.__setattr__(self, "message", str(self.message).strip())
        object.__setattr__(self, "correlation_id", str(self.correlation_id).strip())
        object.__setattr__(self, "source", str(self.source).strip())
        object.__setattr__(self, "detail", _stable_json_value(self.detail))
        self.validate()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HorizonEvent":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            event_id=data.get("event_id", ""),
            ts=data.get("ts", ""),
            actor=data.get("actor", ""),
            horizon_id=data.get("horizon_id"),
            event_type=data.get("event_type", EventType.NOTE.value),
            severity=data.get("severity", EventSeverity.INFO.value),
            message=data.get("message", ""),
            correlation_id=data.get("correlation_id", ""),
            source=data.get("source", ""),
            detail=data.get("detail", {}),
        )

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported event schema_version: {self.schema_version!r}")
        if not self.event_id:
            raise ValueError("event_id is required")
        if not self.ts:
            raise ValueError("ts is required")
        if not self.actor:
            raise ValueError("actor is required")
        if not self.message:
            raise ValueError("message is required")
        if not isinstance(self.detail, dict):
            raise ValueError("detail must be a JSON object")
        json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "detail": self.detail,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "horizon_id": str(self.horizon_id) if self.horizon_id else None,
            "message": self.message,
            "schema_version": self.schema_version,
            "severity": self.severity.value,
            "source": self.source,
            "ts": self.ts,
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


@dataclass(frozen=True)
class EventSummary:
    total: int
    by_type: dict[str, int]
    by_horizon: dict[str, int]
    by_severity: dict[str, int]
    last_event_by_horizon: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_type": self.by_type,
            "by_horizon": self.by_horizon,
            "by_severity": self.by_severity,
            "last_event_by_horizon": self.last_event_by_horizon,
        }


def append_event(path: str | Path, event: HorizonEvent | dict[str, Any], *, fsync: bool = False) -> HorizonEvent:
    parsed = event if isinstance(event, HorizonEvent) else HorizonEvent.from_dict(event)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    line = parsed.to_json_line()
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        if fsync:
            os.fsync(handle.fileno())
    return parsed


def read_events(
    path: str | Path,
    *,
    horizon_id: str | int | None = None,
    event_type: EventType | str | None = None,
) -> Iterator[HorizonEvent]:
    source = Path(path)
    if not source.exists():
        return
    wanted_horizon = str(HorizonId(horizon_id)) if horizon_id is not None else None
    wanted_type = EventType.normalize(event_type).value if event_type is not None else None
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = HorizonEvent.from_dict(json.loads(stripped))
            except (TypeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"invalid event at {source}:{line_number}: {exc}") from exc
            if wanted_horizon is not None and str(event.horizon_id) != wanted_horizon:
                continue
            if wanted_type is not None and event.event_type.value != wanted_type:
                continue
            yield event


def summarize_events(events: Iterable[HorizonEvent | dict[str, Any]]) -> EventSummary:
    parsed = [event if isinstance(event, HorizonEvent) else HorizonEvent.from_dict(event) for event in events]
    by_type = Counter(event.event_type.value for event in parsed)
    by_horizon = Counter(str(event.horizon_id) if event.horizon_id else "global" for event in parsed)
    by_severity = Counter(event.severity.value for event in parsed)
    last_by_horizon: dict[str, HorizonEvent] = {}
    for event in sorted(parsed, key=lambda item: (item.ts, item.event_id)):
        key = str(event.horizon_id) if event.horizon_id else "global"
        last_by_horizon[key] = event
    return EventSummary(
        total=len(parsed),
        by_type={key: by_type[key] for key in sorted(by_type)},
        by_horizon={key: by_horizon[key] for key in sorted(by_horizon, key=_horizon_key)},
        by_severity={severity.value: by_severity.get(severity.value, 0) for severity in EventSeverity},
        last_event_by_horizon={
            key: last_by_horizon[key].to_dict()
            for key in sorted(last_by_horizon, key=_horizon_key)
        },
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_ts(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("ts is required")
    return text


def _stable_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_json_value(item) for item in value]
    json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _horizon_key(value: str) -> tuple[int, str]:
    if value == "global":
        return (0, value)
    return (HorizonId(value).number, value)
