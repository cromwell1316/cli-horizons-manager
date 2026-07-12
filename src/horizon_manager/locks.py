"""Durable horizon lock tracking.

H42 records horizon claims as deterministic JSON so parallel agents can coordinate
without relying on chat context or process memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
import json
from pathlib import Path
from typing import Any, Iterable

from .conflicts import ConflictMatrix, ConflictSeverity
from .model import HorizonId, HorizonState, HorizonStatus


DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "hermes-consistency-orchestrator/horizon_locks.json"
DEFAULT_TTL = timedelta(hours=2)


class LockStatus(Enum):
    ACTIVE = "active"
    STALE = "stale"
    RELEASED = "released"
    REJECTED = "rejected"

    @classmethod
    def normalize(cls, value: str | "LockStatus" | None) -> "LockStatus":
        if isinstance(value, LockStatus):
            return value
        text = (value or "").strip().lower().replace("-", "_")
        aliases = {"claimed": cls.ACTIVE, "running": cls.ACTIVE, "expired": cls.STALE}
        if text in aliases:
            return aliases[text]
        for status in cls:
            if status.value == text:
                return status
        return cls.ACTIVE


@dataclass(frozen=True, order=True)
class LockConflictEvidence:
    horizon_id: HorizonId
    kind: str
    severity: str
    paths: tuple[str, ...] = ()
    explanation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "paths", tuple(sorted(str(path) for path in self.paths)))

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_id": str(self.horizon_id),
            "kind": self.kind,
            "severity": self.severity,
            "paths": list(self.paths),
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LockConflictEvidence":
        return cls(
            horizon_id=data.get("horizon_id") or data.get("other") or data.get("id"),
            kind=str(data.get("kind", "")),
            severity=str(data.get("severity", "")),
            paths=tuple(str(path) for path in data.get("paths", ())),
            explanation=str(data.get("explanation", "")),
        )


@dataclass(frozen=True)
class HorizonLock:
    horizon_id: HorizonId
    agent_id: str
    status: LockStatus = LockStatus.ACTIVE
    claimed_paths: tuple[str, ...] = ()
    claimed_at: str = ""
    expires_at: str = ""
    ttl_seconds: int = 0
    released_at: str = ""
    reason: str = ""
    conflicts: tuple[LockConflictEvidence, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "agent_id", str(self.agent_id).strip() or "unknown-agent")
        if isinstance(self.status, str):
            object.__setattr__(self, "status", LockStatus.normalize(self.status))
        object.__setattr__(self, "claimed_paths", tuple(sorted(str(path) for path in self.claimed_paths)))
        object.__setattr__(self, "conflicts", tuple(sorted(self.conflicts, key=lambda item: (item.horizon_id.number, item.kind, item.severity))))

    @property
    def is_active(self) -> bool:
        return self.status is LockStatus.ACTIVE

    def is_expired(self, now: datetime | str | None = None) -> bool:
        if not self.expires_at:
            return False
        now_dt = _parse_time(now) or _utc_now()
        expires = _parse_time(self.expires_at)
        return expires is not None and expires <= now_dt

    def mark_stale(self, *, now: datetime | str | None = None, reason: str = "ttl expired") -> "HorizonLock":
        del now
        return _replace_lock(self, status=LockStatus.STALE, reason=reason)

    def release(self, *, now: datetime | str | None = None, reason: str = "released by owner") -> "HorizonLock":
        return _replace_lock(self, status=LockStatus.RELEASED, released_at=_format_time(now), reason=reason)

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_id": str(self.horizon_id),
            "agent_id": self.agent_id,
            "status": self.status.value,
            "claimed_paths": list(self.claimed_paths),
            "claimed_at": self.claimed_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "released_at": self.released_at,
            "reason": self.reason,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HorizonLock":
        return cls(
            horizon_id=data.get("horizon_id") or data.get("horizon") or data.get("id"),
            agent_id=data.get("agent_id") or data.get("owner") or "unknown-agent",
            status=LockStatus.normalize(data.get("status")),
            claimed_paths=tuple(str(path) for path in data.get("claimed_paths", data.get("paths", ()))),
            claimed_at=str(data.get("claimed_at", "")),
            expires_at=str(data.get("expires_at", "")),
            ttl_seconds=int(data.get("ttl_seconds") or data.get("ttl") or 0),
            released_at=str(data.get("released_at", "")),
            reason=str(data.get("reason", "")),
            conflicts=tuple(LockConflictEvidence.from_dict(item) for item in data.get("conflicts", ())),
        )


@dataclass(frozen=True)
class LockDecision:
    ok: bool
    lock: HorizonLock | None = None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blockers", tuple(sorted(set(self.blockers))))
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "lock": self.lock.to_dict() if self.lock else None,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


@dataclass
class LockSnapshot:
    locks: tuple[HorizonLock, ...] = ()
    generated_at: str = ""
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.locks = tuple(sorted(self.locks, key=_lock_sort_key))
        self.metadata = _stable_value(self.metadata)

    @property
    def active_locks(self) -> tuple[HorizonLock, ...]:
        return tuple(lock for lock in self.locks if lock.status is LockStatus.ACTIVE)

    def status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in LockStatus}
        for lock in self.locks:
            counts[lock.status.value] += 1
        return counts

    def status_for_horizon(self, horizon_id: str | int) -> tuple[HorizonLock, ...]:
        wanted = HorizonId(horizon_id)
        return tuple(lock for lock in self.locks if lock.horizon_id == wanted)

    def active_for_horizon(self, horizon_id: str | int, *, now: datetime | str | None = None) -> tuple[HorizonLock, ...]:
        wanted = HorizonId(horizon_id)
        return tuple(lock for lock in self.locks if lock.horizon_id == wanted and lock.status is LockStatus.ACTIVE and not lock.is_expired(now))

    def with_lock(self, lock: HorizonLock, *, generated_at: datetime | str | None = None) -> "LockSnapshot":
        return LockSnapshot(
            locks=(*self.locks, lock),
            generated_at=_format_time(generated_at),
            schema_version=self.schema_version,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "lock_count": len(self.locks),
            "status_counts": self.status_counts(),
            "locks": [lock.to_dict() for lock in self.locks],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LockSnapshot":
        rows = data.get("locks") or data.get("active_locks") or data.get("records") or data.get("claims") or ()
        return cls(
            locks=tuple(HorizonLock.from_dict(row) for row in rows),
            generated_at=str(data.get("generated_at", "")),
            schema_version=int(data.get("schema_version", 1)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class LockStore:
    path: Path = DEFAULT_OUTPUT

    def load(self) -> LockSnapshot:
        if not self.path.exists():
            return LockSnapshot(metadata={"source": str(self.path), "missing": True})
        return LockSnapshot.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, snapshot: LockSnapshot) -> LockSnapshot:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(snapshot.to_json(), encoding="utf-8")
        return snapshot


def claim_horizon(
    state: HorizonState,
    conflicts: ConflictMatrix | None,
    locks: LockSnapshot | dict[str, Any] | Iterable[HorizonLock | dict[str, Any]] | None,
    horizon_id: str | int,
    agent_id: str,
    ttl: int | float | timedelta = DEFAULT_TTL,
    *,
    now: datetime | str | None = None,
) -> tuple[LockSnapshot, LockDecision]:
    snapshot = prune_stale_locks(_coerce_snapshot(locks), now=now)
    record = state.get(horizon_id)
    if record is None:
        return _reject(snapshot, horizon_id, agent_id, "unknown horizon", now=now, blockers=(f"missing:{HorizonId(horizon_id)}",))

    blockers: list[str] = []
    if record.status is not HorizonStatus.PLANNED:
        blockers.append(f"status:{record.status.value}")

    implemented = {item.id for item in state.records if item.status is HorizonStatus.IMPLEMENTED}
    missing = tuple(dependency.id for dependency in record.dependencies if dependency.id not in implemented)
    blockers.extend(f"dependency:{dependency}" for dependency in missing)

    for active in snapshot.active_for_horizon(record.id, now=now):
        if active.agent_id == str(agent_id):
            return snapshot, LockDecision(ok=True, lock=active, warnings=("already claimed by same agent",))
        blockers.append(f"lock:{active.agent_id}")

    evidence = _conflict_evidence(record.id, conflicts, snapshot, now=now)
    blockers.extend(f"conflict:{conflict.horizon_id}" for conflict in evidence)

    if blockers:
        reason = "; ".join(blockers)
        return _reject(snapshot, record.id, agent_id, reason, now=now, blockers=tuple(blockers), conflicts=evidence)

    ttl_delta = _ttl_delta(ttl)
    claimed_at = _format_time(now)
    expires_at = _format_time((_parse_time(now) or _utc_now()) + ttl_delta)
    lock = HorizonLock(
        horizon_id=record.id,
        agent_id=agent_id,
        status=LockStatus.ACTIVE,
        claimed_paths=tuple(path.path for path in record.owned_files),
        claimed_at=claimed_at,
        expires_at=expires_at,
        ttl_seconds=int(ttl_delta.total_seconds()),
        reason="claimed",
    )
    next_snapshot = snapshot.with_lock(lock, generated_at=now)
    return next_snapshot, LockDecision(ok=True, lock=lock)


def release_horizon(
    locks: LockSnapshot | dict[str, Any] | Iterable[HorizonLock | dict[str, Any]] | None,
    horizon_id: str | int,
    agent_id: str,
    *,
    now: datetime | str | None = None,
) -> tuple[LockSnapshot, LockDecision]:
    snapshot = _coerce_snapshot(locks)
    wanted = HorizonId(horizon_id)
    changed: list[HorizonLock] = []
    released: HorizonLock | None = None
    owner_blockers: list[str] = []
    for lock in snapshot.locks:
        if lock.horizon_id != wanted or lock.status is not LockStatus.ACTIVE:
            changed.append(lock)
            continue
        if lock.agent_id != str(agent_id):
            owner_blockers.append(f"owner:{lock.agent_id}")
            changed.append(lock)
            continue
        released = lock.release(now=now)
        changed.append(released)

    if released is None:
        blockers = tuple(owner_blockers or (f"not_active:{wanted}",))
        return LockSnapshot(tuple(changed), generated_at=_format_time(now), schema_version=snapshot.schema_version, metadata=snapshot.metadata), LockDecision(False, blockers=blockers)

    next_snapshot = LockSnapshot(tuple(changed), generated_at=_format_time(now), schema_version=snapshot.schema_version, metadata=snapshot.metadata)
    return next_snapshot, LockDecision(True, lock=released)


def prune_stale_locks(
    locks: LockSnapshot | dict[str, Any] | Iterable[HorizonLock | dict[str, Any]] | None,
    *,
    now: datetime | str | None = None,
) -> LockSnapshot:
    snapshot = _coerce_snapshot(locks)
    changed: list[HorizonLock] = []
    has_transition = False
    for lock in snapshot.locks:
        if lock.status is LockStatus.ACTIVE and lock.is_expired(now):
            changed.append(lock.mark_stale(now=now))
            has_transition = True
        else:
            changed.append(lock)
    if not has_transition:
        return snapshot
    return LockSnapshot(changed, generated_at=_format_time(now), schema_version=snapshot.schema_version, metadata=snapshot.metadata)


def status_for_horizon(
    locks: LockSnapshot | dict[str, Any] | Iterable[HorizonLock | dict[str, Any]] | None,
    horizon_id: str | int,
) -> tuple[HorizonLock, ...]:
    return _coerce_snapshot(locks).status_for_horizon(horizon_id)


def write_initial_snapshot(output_path: str | Path = DEFAULT_OUTPUT, *, now: datetime | str | None = None) -> LockSnapshot:
    snapshot = LockSnapshot(generated_at=_format_time(now), metadata={"source": "H42 initial empty lock snapshot"})
    snapshot.write_json(output_path)
    return snapshot


def _reject(
    snapshot: LockSnapshot,
    horizon_id: str | int,
    agent_id: str,
    reason: str,
    *,
    now: datetime | str | None,
    blockers: tuple[str, ...],
    conflicts: tuple[LockConflictEvidence, ...] = (),
) -> tuple[LockSnapshot, LockDecision]:
    lock = HorizonLock(
        horizon_id=horizon_id,
        agent_id=agent_id,
        status=LockStatus.REJECTED,
        claimed_at=_format_time(now),
        reason=reason,
        conflicts=conflicts,
    )
    next_snapshot = snapshot.with_lock(lock, generated_at=now)
    return next_snapshot, LockDecision(ok=False, lock=lock, blockers=blockers)


def _conflict_evidence(
    horizon_id: HorizonId,
    conflicts: ConflictMatrix | None,
    snapshot: LockSnapshot,
    *,
    now: datetime | str | None,
) -> tuple[LockConflictEvidence, ...]:
    if conflicts is None:
        return ()
    active = {lock.horizon_id for lock in snapshot.active_locks if not lock.is_expired(now)}
    evidence: list[LockConflictEvidence] = []
    for conflict in conflicts.blockers_by_horizon.get(horizon_id, ()):
        if conflict.severity is not ConflictSeverity.BLOCK:
            continue
        other = conflict.other(horizon_id)
        if other not in active:
            continue
        evidence.append(
            LockConflictEvidence(
                horizon_id=other,
                kind=conflict.kind.value,
                severity=conflict.severity.value,
                paths=tuple(path.path for path in conflict.paths),
                explanation=conflict.explanation,
            )
        )
    return tuple(sorted(evidence, key=lambda item: item.horizon_id.number))


def _coerce_snapshot(source: LockSnapshot | dict[str, Any] | Iterable[HorizonLock | dict[str, Any]] | None) -> LockSnapshot:
    if source is None:
        return LockSnapshot()
    if isinstance(source, LockSnapshot):
        return source
    if isinstance(source, dict):
        if any(key in source for key in ("locks", "active_locks", "records", "claims")):
            return LockSnapshot.from_dict(source)
        if "horizon_id" in source or "horizon" in source:
            return LockSnapshot((HorizonLock.from_dict(source),))
        return LockSnapshot()
    rows: list[HorizonLock] = []
    for row in source:
        rows.append(row if isinstance(row, HorizonLock) else HorizonLock.from_dict(row))
    return LockSnapshot(tuple(rows))


def _replace_lock(lock: HorizonLock, **changes: Any) -> HorizonLock:
    data = lock.to_dict()
    data.update({key: (value.value if isinstance(value, LockStatus) else value) for key, value in changes.items()})
    return HorizonLock.from_dict(data)


def _lock_sort_key(lock: HorizonLock) -> tuple[int, str, str, str, str]:
    return (lock.horizon_id.number, lock.status.value, lock.claimed_at, lock.agent_id, lock.reason)


def _ttl_delta(ttl: int | float | timedelta) -> timedelta:
    if isinstance(ttl, timedelta):
        return ttl
    return timedelta(seconds=int(ttl))


def _format_time(value: datetime | str | None) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        value = _utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_time(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    return value
