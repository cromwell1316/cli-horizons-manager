"""Deterministic Horizon Manager snapshots and change history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
DEFAULT_SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "management/horizon_snapshots"


@dataclass(frozen=True)
class Snapshot:
    """Compact immutable view of one Horizon Manager render state."""

    snapshot_id: str
    created_at: str
    state_hash: str
    event_offset: int
    dashboard_hash: str
    horizon_summary: dict[str, Any]
    conflict_summary: tuple[dict[str, Any], ...] = ()
    lock_summary: tuple[dict[str, Any], ...] = ()
    recommendations: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", str(self.snapshot_id).strip())
        object.__setattr__(self, "created_at", _normalize_ts(self.created_at))
        object.__setattr__(self, "state_hash", str(self.state_hash).strip())
        object.__setattr__(self, "event_offset", int(self.event_offset))
        object.__setattr__(self, "dashboard_hash", str(self.dashboard_hash).strip())
        object.__setattr__(self, "horizon_summary", _stable_value(self.horizon_summary))
        object.__setattr__(self, "conflict_summary", tuple(_stable_value(row) for row in self.conflict_summary))
        object.__setattr__(self, "lock_summary", tuple(_stable_value(row) for row in self.lock_summary))
        object.__setattr__(self, "recommendations", tuple(sorted(str(item) for item in self.recommendations)))
        object.__setattr__(self, "event_ids", tuple(sorted(str(item) for item in self.event_ids)))
        object.__setattr__(self, "metadata", _stable_value(self.metadata))
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot schema_version: {self.schema_version!r}")
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")

    @property
    def id(self) -> str:
        return self.snapshot_id

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Snapshot":
        return cls(
            snapshot_id=str(data.get("snapshot_id", data.get("id", ""))),
            created_at=str(data.get("created_at", "")),
            state_hash=str(data.get("state_hash", "")),
            event_offset=int(data.get("event_offset", 0)),
            dashboard_hash=str(data.get("dashboard_hash", "")),
            horizon_summary=dict(data.get("horizon_summary", {})),
            conflict_summary=tuple(dict(row) for row in data.get("conflict_summary", ())),
            lock_summary=tuple(dict(row) for row in data.get("lock_summary", ())),
            recommendations=tuple(str(item) for item in data.get("recommendations", ())),
            event_ids=tuple(str(item) for item in data.get("event_ids", ())),
            metadata=dict(data.get("metadata", {})),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at,
            "state_hash": self.state_hash,
            "event_offset": self.event_offset,
            "dashboard_hash": self.dashboard_hash,
            "horizon_summary": self.horizon_summary,
            "conflict_summary": list(self.conflict_summary),
            "lock_summary": list(self.lock_summary),
            "recommendations": list(self.recommendations),
            "event_ids": list(self.event_ids),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class SnapshotIndex:
    snapshots: tuple[Snapshot, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshots", tuple(sorted(self.snapshots, key=lambda item: (item.created_at, item.snapshot_id))))
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    @property
    def latest(self) -> Snapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostics": list(self.diagnostics),
            "snapshot_count": len(self.snapshots),
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }


@dataclass(frozen=True)
class ChangeSet:
    previous_id: str | None = None
    current_id: str | None = None
    status_transitions: tuple[dict[str, Any], ...] = ()
    new_blockers: tuple[dict[str, Any], ...] = ()
    resolved_blockers: tuple[dict[str, Any], ...] = ()
    new_conflicts: tuple[dict[str, Any], ...] = ()
    resolved_conflicts: tuple[dict[str, Any], ...] = ()
    new_locks: tuple[dict[str, Any], ...] = ()
    resolved_locks: tuple[dict[str, Any], ...] = ()
    new_recommendations: tuple[str, ...] = ()
    removed_recommendations: tuple[str, ...] = ()
    event_delta: int = 0
    new_event_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "status_transitions",
            "new_blockers",
            "resolved_blockers",
            "new_conflicts",
            "resolved_conflicts",
            "new_locks",
            "resolved_locks",
        ):
            object.__setattr__(self, name, tuple(_stable_value(row) for row in getattr(self, name)))
        object.__setattr__(self, "new_recommendations", tuple(sorted(str(item) for item in self.new_recommendations)))
        object.__setattr__(self, "removed_recommendations", tuple(sorted(str(item) for item in self.removed_recommendations)))
        object.__setattr__(self, "new_event_ids", tuple(sorted(str(item) for item in self.new_event_ids)))
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    @property
    def has_changes(self) -> bool:
        return any(
            (
                self.status_transitions,
                self.new_blockers,
                self.resolved_blockers,
                self.new_conflicts,
                self.resolved_conflicts,
                self.new_locks,
                self.resolved_locks,
                self.new_recommendations,
                self.removed_recommendations,
                self.event_delta,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_id": self.previous_id,
            "current_id": self.current_id,
            "status_transitions": list(self.status_transitions),
            "new_blockers": list(self.new_blockers),
            "resolved_blockers": list(self.resolved_blockers),
            "new_conflicts": list(self.new_conflicts),
            "resolved_conflicts": list(self.resolved_conflicts),
            "new_locks": list(self.new_locks),
            "resolved_locks": list(self.resolved_locks),
            "new_recommendations": list(self.new_recommendations),
            "removed_recommendations": list(self.removed_recommendations),
            "event_delta": self.event_delta,
            "new_event_ids": list(self.new_event_ids),
            "diagnostics": list(self.diagnostics),
            "has_changes": self.has_changes,
        }


def build_snapshot(
    *,
    state: Any,
    conflicts: Any = None,
    locks: Any = None,
    recommendations: Any = None,
    events: Iterable[Any] | None = None,
    dashboard: Any = "",
    created_at: datetime | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Snapshot:
    """Build a compact deterministic snapshot from Horizon Manager objects."""

    state_data = _to_dict(state)
    conflict_data = _to_dict(conflicts) if conflicts is not None else {}
    lock_data = _to_dict(locks) if locks is not None else {}
    recommendation_data = _to_dict(recommendations) if recommendations is not None else {}
    event_rows = tuple(_to_dict(event) for event in (events or ()))
    created = _format_ts(created_at)
    horizon_summary = _horizon_summary(state_data, conflict_data, lock_data, recommendation_data)
    conflict_summary = _conflict_rows(conflict_data)
    lock_summary = _lock_rows(lock_data)
    recommendation_ids = tuple(row["horizon_id"] for row in _recommendation_rows(recommendation_data))
    event_ids = tuple(str(row.get("event_id", "")) for row in event_rows if row.get("event_id"))
    state_hash = _hash_json(state_data)
    dashboard_hash = _hash_json(_to_dict(dashboard) if not isinstance(dashboard, str) else dashboard)
    snapshot_id = _snapshot_id(created, state_hash, dashboard_hash, len(event_rows), horizon_summary, conflict_summary, lock_summary, recommendation_ids)
    return Snapshot(
        snapshot_id=snapshot_id,
        created_at=created,
        state_hash=state_hash,
        event_offset=len(event_rows),
        dashboard_hash=dashboard_hash,
        horizon_summary=horizon_summary,
        conflict_summary=conflict_summary,
        lock_summary=lock_summary,
        recommendations=recommendation_ids,
        event_ids=event_ids,
        metadata=metadata or {},
    )


def write_snapshot(snapshot_dir: str | Path, snapshot: Snapshot) -> Path:
    destination_dir = Path(snapshot_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / snapshot_filename(snapshot)
    if destination.exists():
        existing = read_snapshot(destination)
        if existing.to_dict() != snapshot.to_dict():
            raise FileExistsError(f"snapshot already exists with different content: {destination}")
    else:
        destination.write_text(snapshot.to_json(), encoding="utf-8")
    return destination


def read_snapshot(path: str | Path) -> Snapshot:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid snapshot {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"invalid snapshot {source}: root must be object")
    try:
        return Snapshot.from_dict(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid snapshot {source}: {exc}") from exc


def list_snapshots(snapshot_dir: str | Path) -> SnapshotIndex:
    source_dir = Path(snapshot_dir)
    if not source_dir.exists():
        return SnapshotIndex()
    snapshots: list[Snapshot] = []
    diagnostics: list[str] = []
    for path in sorted(source_dir.glob("*.json")):
        try:
            snapshots.append(read_snapshot(path))
        except ValueError as exc:
            diagnostics.append(str(exc))
    return SnapshotIndex(tuple(snapshots), tuple(diagnostics))


def diff_snapshots(previous: Snapshot | dict[str, Any] | None, current: Snapshot | dict[str, Any]) -> ChangeSet:
    current_snapshot = _coerce_snapshot(current)
    if previous is None:
        return ChangeSet(current_id=current_snapshot.snapshot_id, event_delta=current_snapshot.event_offset, new_event_ids=current_snapshot.event_ids)
    previous_snapshot = _coerce_snapshot(previous)
    previous_horizons = _horizons_by_id(previous_snapshot)
    current_horizons = _horizons_by_id(current_snapshot)
    return ChangeSet(
        previous_id=previous_snapshot.snapshot_id,
        current_id=current_snapshot.snapshot_id,
        status_transitions=_status_transitions(previous_horizons, current_horizons),
        new_blockers=_set_rows(_blocker_keys(current_snapshot) - _blocker_keys(previous_snapshot)),
        resolved_blockers=_set_rows(_blocker_keys(previous_snapshot) - _blocker_keys(current_snapshot)),
        new_conflicts=_set_rows(_conflict_keys(current_snapshot) - _conflict_keys(previous_snapshot)),
        resolved_conflicts=_set_rows(_conflict_keys(previous_snapshot) - _conflict_keys(current_snapshot)),
        new_locks=_set_rows(_lock_keys(current_snapshot) - _lock_keys(previous_snapshot)),
        resolved_locks=_set_rows(_lock_keys(previous_snapshot) - _lock_keys(current_snapshot)),
        new_recommendations=tuple(set(current_snapshot.recommendations) - set(previous_snapshot.recommendations)),
        removed_recommendations=tuple(set(previous_snapshot.recommendations) - set(current_snapshot.recommendations)),
        event_delta=max(0, current_snapshot.event_offset - previous_snapshot.event_offset),
        new_event_ids=tuple(set(current_snapshot.event_ids) - set(previous_snapshot.event_ids)),
    )


def summarize_since_last(snapshot_dir: str | Path, current: Snapshot | dict[str, Any]) -> ChangeSet:
    current_snapshot = _coerce_snapshot(current)
    index = list_snapshots(snapshot_dir)
    previous = None
    for snapshot in reversed(index.snapshots):
        if snapshot.snapshot_id != current_snapshot.snapshot_id:
            previous = snapshot
            break
    changes = diff_snapshots(previous, current_snapshot)
    if index.diagnostics:
        return ChangeSet(
            previous_id=changes.previous_id,
            current_id=changes.current_id,
            status_transitions=changes.status_transitions,
            new_blockers=changes.new_blockers,
            resolved_blockers=changes.resolved_blockers,
            new_conflicts=changes.new_conflicts,
            resolved_conflicts=changes.resolved_conflicts,
            new_locks=changes.new_locks,
            resolved_locks=changes.resolved_locks,
            new_recommendations=changes.new_recommendations,
            removed_recommendations=changes.removed_recommendations,
            event_delta=changes.event_delta,
            new_event_ids=changes.new_event_ids,
            diagnostics=index.diagnostics,
        )
    return changes


def snapshot_filename(snapshot: Snapshot) -> str:
    safe_ts = snapshot.created_at.replace(":", "").replace("-", "").replace("Z", "Z")
    return f"snapshot-{safe_ts}-{snapshot.snapshot_id}.json"


def _horizon_summary(state: dict[str, Any], conflicts: dict[str, Any], locks: dict[str, Any], recommendations: dict[str, Any]) -> dict[str, Any]:
    blockers = _blockers_by_horizon(conflicts)
    active_locks = _active_lock_agents_by_horizon(locks)
    start_now = {row["horizon_id"] for row in _recommendation_rows(recommendations)}
    rows: dict[str, Any] = {}
    for record in _state_records(state):
        horizon_id = str(record.get("id") or record.get("horizon_id"))
        if not horizon_id:
            continue
        rows[horizon_id] = {
            "title": str(record.get("title", "")),
            "status": str(record.get("status", "unknown")),
            "wave": record.get("wave"),
            "blockers": blockers.get(horizon_id, ()),
            "active_locks": active_locks.get(horizon_id, ()),
            "start_now": horizon_id in start_now,
        }
    return rows


def _state_records(state: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = state.get("horizons", state.get("records", ()))
    return tuple(_stable_value(dict(row)) for row in rows)


def _conflict_rows(conflicts: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = conflicts.get("conflicts", ())
    result = []
    for row in rows:
        left = str(row.get("left", ""))
        right = str(row.get("right", ""))
        if not left or not right:
            continue
        result.append(
            {
                "left": left,
                "right": right,
                "kind": str(row.get("kind", "")),
                "severity": str(row.get("severity", "")),
            }
        )
    return tuple(sorted(result, key=lambda item: (item["left"], item["right"], item["kind"], item["severity"])))


def _lock_rows(locks: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = locks.get("locks", locks.get("active_locks", ()))
    result = []
    for row in rows:
        horizon_id = str(row.get("horizon_id", row.get("horizon", "")))
        agent_id = str(row.get("agent_id", row.get("owner", "")))
        status = str(row.get("status", "active"))
        if not horizon_id or not agent_id:
            continue
        result.append({"horizon_id": horizon_id, "agent_id": agent_id, "status": status})
    return tuple(sorted(result, key=lambda item: (item["horizon_id"], item["agent_id"], item["status"])))


def _recommendation_rows(recommendations: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = recommendations.get("recommendations", ())
    result = []
    for row in rows:
        horizon_id = str(row.get("horizon_id", row.get("id", "")))
        if horizon_id:
            result.append({"horizon_id": horizon_id, "rank": int(row.get("rank", 0))})
    return tuple(sorted(result, key=lambda item: (item["rank"], item["horizon_id"])))


def _blockers_by_horizon(conflicts: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    blockers: dict[str, set[str]] = {}
    for row in _conflict_rows(conflicts):
        if row["severity"] not in {"block", "error", "critical", "fatal"}:
            continue
        blockers.setdefault(row["left"], set()).add(f"conflict:{row['right']}")
        blockers.setdefault(row["right"], set()).add(f"conflict:{row['left']}")
    explicit = conflicts.get("blockers_by_horizon", {})
    if isinstance(explicit, dict):
        for horizon_id, rows in explicit.items():
            for row in rows:
                other = row.get("right") if row.get("left") == horizon_id else row.get("left")
                if other:
                    blockers.setdefault(str(horizon_id), set()).add(f"conflict:{other}")
    return {key: tuple(sorted(values)) for key, values in sorted(blockers.items())}


def _active_lock_agents_by_horizon(locks: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    active: dict[str, set[str]] = {}
    for row in _lock_rows(locks):
        if row["status"] not in {"active", "claimed", "running"}:
            continue
        active.setdefault(row["horizon_id"], set()).add(row["agent_id"])
    return {key: tuple(sorted(values)) for key, values in sorted(active.items())}


def _horizons_by_id(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    return {str(key): dict(value) for key, value in snapshot.horizon_summary.items()}


def _status_transitions(previous: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    rows = []
    for horizon_id in sorted(set(previous) & set(current)):
        before = previous[horizon_id].get("status")
        after = current[horizon_id].get("status")
        if before != after:
            rows.append({"horizon_id": horizon_id, "from": before, "to": after})
    return tuple(rows)


def _blocker_keys(snapshot: Snapshot) -> set[tuple[str, str]]:
    keys = set()
    for horizon_id, row in snapshot.horizon_summary.items():
        for blocker in row.get("blockers", ()):
            keys.add((str(horizon_id), str(blocker)))
    return keys


def _conflict_keys(snapshot: Snapshot) -> set[tuple[str, str, str, str]]:
    return {(row["left"], row["right"], row["kind"], row["severity"]) for row in snapshot.conflict_summary}


def _lock_keys(snapshot: Snapshot) -> set[tuple[str, str, str]]:
    return {(row["horizon_id"], row["agent_id"], row["status"]) for row in snapshot.lock_summary}


def _set_rows(values: set[tuple[Any, ...]]) -> tuple[dict[str, Any], ...]:
    rows = []
    for value in sorted(values):
        if len(value) == 2:
            rows.append({"horizon_id": value[0], "value": value[1]})
        elif len(value) == 3:
            rows.append({"horizon_id": value[0], "agent_id": value[1], "status": value[2]})
        elif len(value) == 4:
            rows.append({"left": value[0], "right": value[1], "kind": value[2], "severity": value[3]})
        else:
            rows.append({"value": list(value)})
    return tuple(rows)


def _coerce_snapshot(value: Snapshot | dict[str, Any]) -> Snapshot:
    return value if isinstance(value, Snapshot) else Snapshot.from_dict(value)


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return _stable_value(value)
    if hasattr(value, "to_dict"):
        return _stable_value(value.to_dict())
    return _stable_value(dict(value))


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _hash_json(value: Any) -> str:
    payload = json.dumps(_stable_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _snapshot_id(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(_stable_value(parts), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _format_ts(value: datetime | str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return _normalize_ts(value)


def _normalize_ts(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("created_at is required")
    return text
