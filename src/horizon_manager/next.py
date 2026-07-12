"""Horizon recommendation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import json
from typing import Any, Iterable

from .conflicts import ConflictMatrix, ConflictSeverity
from .model import HorizonId, HorizonRecord, HorizonState, HorizonStatus, OwnedPathMode


DOCTOR_BLOCK_SEVERITIES = frozenset({"block", "error", "critical", "fatal"})
ACTIVE_LOCK_STATUSES = frozenset({"active", "claimed", "running"})


class ExclusionReason(Enum):
    NOT_PLANNED = "not_planned"
    DEPENDENCY_NOT_READY = "dependency_not_ready"
    DOCTOR_BLOCKER = "doctor_blocker"
    ACTIVE_LOCK = "active_lock"
    ACTIVE_CONFLICT = "active_conflict"


@dataclass(frozen=True)
class RecommendationScore:
    readiness: float
    lock_available: float
    conflict_safety: float
    unblock_value: float
    wave_priority: float
    blast_radius: float
    total: float = 0.0

    def __post_init__(self) -> None:
        total = (
            self.readiness * 30.0
            + self.lock_available * 20.0
            + self.conflict_safety * 15.0
            + self.unblock_value * 15.0
            + self.wave_priority * 10.0
            + self.blast_radius * 10.0
        )
        object.__setattr__(self, "total", _round(total if self.total == 0.0 else self.total))

    def to_dict(self) -> dict[str, float]:
        return {
            "readiness": _round(self.readiness),
            "lock_available": _round(self.lock_available),
            "conflict_safety": _round(self.conflict_safety),
            "unblock_value": _round(self.unblock_value),
            "wave_priority": _round(self.wave_priority),
            "blast_radius": _round(self.blast_radius),
            "total": _round(self.total),
        }


@dataclass(frozen=True)
class Recommendation:
    horizon_id: HorizonId
    title: str
    rank: int
    score: RecommendationScore
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    explanation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "blockers", tuple(sorted(set(self.blockers))))
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_id": str(self.horizon_id),
            "title": self.title,
            "rank": self.rank,
            "score": self.score.to_dict(),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class ExcludedHorizon:
    horizon_id: HorizonId
    title: str
    reasons: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))
        object.__setattr__(self, "blockers", tuple(sorted(set(self.blockers))))

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_id": str(self.horizon_id),
            "title": self.title,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
        }


@dataclass
class RecommendationReport:
    recommendations: tuple[Recommendation, ...]
    excluded: tuple[ExcludedHorizon, ...] = ()
    generated_at: str = ""
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.recommendations = tuple(sorted(self.recommendations, key=lambda item: item.rank))
        self.excluded = tuple(sorted(self.excluded, key=lambda item: item.horizon_id.number))
        self.metadata = {str(key): self.metadata[key] for key in sorted(self.metadata)}

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "recommendation_count": len(self.recommendations),
            "excluded_count": len(self.excluded),
            "recommendations": [recommendation.to_dict() for recommendation in self.recommendations],
            "excluded": [excluded.to_dict() for excluded in self.excluded],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def recommend_next(
    state: HorizonState,
    doctor_report: Any = None,
    conflict_matrix: ConflictMatrix | None = None,
    locks: Any = None,
    *,
    now: datetime | str | None = None,
    limit: int | None = None,
) -> RecommendationReport:
    generated_at = _format_time(now)
    implemented = {record.id for record in state.records if record.status is HorizonStatus.IMPLEMENTED}
    diagnostics = _blocking_diagnostics_by_horizon(doctor_report)
    active_locks = _active_locks_by_horizon(locks, now=now)
    max_wave = max((record.wave or 0 for record in state.records), default=0)
    dependency_depths = _dependency_depths(state)

    candidates: list[tuple[Recommendation, tuple[float, int, int, int]]] = []
    excluded: list[ExcludedHorizon] = []
    for record in state.records:
        reasons, blockers = _exclusion_reasons(
            record,
            implemented=implemented,
            diagnostics=diagnostics,
            active_locks=active_locks,
            conflict_matrix=conflict_matrix,
        )
        if reasons:
            excluded.append(ExcludedHorizon(record.id, record.title, tuple(reason.value for reason in reasons), tuple(blockers)))
            continue

        score = _score_record(
            state,
            record,
            conflict_matrix=conflict_matrix,
            max_wave=max_wave,
        )
        recommendation = Recommendation(
            horizon_id=record.id,
            title=record.title,
            rank=0,
            score=score,
            warnings=_warnings_for(record, conflict_matrix),
            explanation="",
        )
        sort_key = (-score.total, record.wave or 10_000, dependency_depths.get(record.id, 0), record.id.number)
        candidates.append((recommendation, sort_key))

    ranked: list[Recommendation] = []
    for rank, (recommendation, _sort_key) in enumerate(sorted(candidates, key=lambda item: item[1]), start=1):
        if limit is not None and rank > limit:
            break
        ranked.append(
            Recommendation(
                horizon_id=recommendation.horizon_id,
                title=recommendation.title,
                rank=rank,
                score=recommendation.score,
                blockers=recommendation.blockers,
                warnings=recommendation.warnings,
                explanation=explain_recommendation(recommendation, rank=rank),
            )
        )

    return RecommendationReport(
        recommendations=tuple(ranked),
        excluded=tuple(excluded),
        generated_at=generated_at,
        metadata={
            "active_locks": len(active_locks),
            "doctor_blocked_horizons": len(diagnostics),
            "horizon_count": len(state.records),
        },
    )


def explain_recommendation(recommendation: Recommendation, *, rank: int | None = None) -> str:
    prefix = f"#{rank or recommendation.rank} {recommendation.horizon_id}"
    return (
        f"{prefix} is ready: dependencies are implemented, no active lock blocks it, "
        f"and score={_round(recommendation.score.total)}."
    )


def _exclusion_reasons(
    record: HorizonRecord,
    *,
    implemented: set[HorizonId],
    diagnostics: dict[HorizonId, tuple[str, ...]],
    active_locks: dict[HorizonId, tuple[str, ...]],
    conflict_matrix: ConflictMatrix | None,
) -> tuple[list[ExclusionReason], list[str]]:
    reasons: list[ExclusionReason] = []
    blockers: list[str] = []
    if record.status is not HorizonStatus.PLANNED:
        reasons.append(ExclusionReason.NOT_PLANNED)
        blockers.append(f"status:{record.status.value}")

    missing_deps = tuple(dependency.id for dependency in record.dependencies if dependency.id not in implemented)
    if missing_deps:
        reasons.append(ExclusionReason.DEPENDENCY_NOT_READY)
        blockers.extend(f"dependency:{dependency}" for dependency in missing_deps)

    for diagnostic in diagnostics.get(record.id, ()):
        reasons.append(ExclusionReason.DOCTOR_BLOCKER)
        blockers.append(f"doctor:{diagnostic}")

    for lock in active_locks.get(record.id, ()):
        reasons.append(ExclusionReason.ACTIVE_LOCK)
        blockers.append(f"lock:{lock}")

    if conflict_matrix is not None:
        for other in conflict_matrix.cannot_run_with(record.id):
            if other not in active_locks:
                continue
            reasons.append(ExclusionReason.ACTIVE_CONFLICT)
            blockers.append(f"conflict:{other}")

    return reasons, blockers


def _score_record(
    state: HorizonState,
    record: HorizonRecord,
    *,
    conflict_matrix: ConflictMatrix | None,
    max_wave: int,
) -> RecommendationScore:
    conflict_blockers = len(conflict_matrix.cannot_run_with(record.id)) if conflict_matrix is not None else 0
    return RecommendationScore(
        readiness=1.0,
        lock_available=1.0,
        conflict_safety=1.0 / (1.0 + conflict_blockers),
        unblock_value=_unblock_value(state, record),
        wave_priority=_wave_priority(record.wave, max_wave),
        blast_radius=_blast_radius(record),
    )


def _unblock_value(state: HorizonState, record: HorizonRecord) -> float:
    implemented = {item.id for item in state.records if item.status is HorizonStatus.IMPLEMENTED}
    hypothetical = {*implemented, record.id}
    unblocked = 0
    planned = 0
    for candidate in state.records:
        if candidate.status is not HorizonStatus.PLANNED or candidate.id == record.id:
            continue
        deps = {dependency.id for dependency in candidate.dependencies}
        if record.id not in deps:
            continue
        planned += 1
        if deps <= hypothetical:
            unblocked += 1
    if planned == 0:
        return 0.0
    return unblocked / planned


def _wave_priority(wave: int | None, max_wave: int) -> float:
    if wave is None or max_wave <= 0:
        return 0.0
    return max(0.0, (max_wave - wave + 1) / max_wave)


def _blast_radius(record: HorizonRecord) -> float:
    weight = 0.0
    for owned in record.owned_files:
        if owned.mode is OwnedPathMode.READ_ONLY:
            weight += 0.25
        elif owned.mode is OwnedPathMode.SHARED:
            weight += 1.5
        elif owned.mode is OwnedPathMode.GENERATED:
            weight += 2.0
        else:
            weight += 1.0
    return 1.0 / (1.0 + weight)


def _warnings_for(record: HorizonRecord, conflict_matrix: ConflictMatrix | None) -> tuple[str, ...]:
    warnings = [f"parse:{warning.code}" for warning in record.warnings]
    if conflict_matrix is not None:
        conflicts = conflict_matrix.cannot_run_with(record.id)
        if conflicts:
            warnings.append(f"conflicts:{len(conflicts)}")
    return tuple(warnings)


def _blocking_diagnostics_by_horizon(report: Any) -> dict[HorizonId, tuple[str, ...]]:
    diagnostics = _extract_sequence(report, ("diagnostics", "issues", "findings"))
    by_horizon: dict[HorizonId, list[str]] = {}
    for diagnostic in diagnostics:
        severity = _text_value(_get_value(diagnostic, "severity", "")).lower()
        if severity not in DOCTOR_BLOCK_SEVERITIES:
            continue
        raw_id = _get_value(diagnostic, "horizon_id", None) or _get_value(diagnostic, "id", None)
        if raw_id is None:
            continue
        code = _text_value(_get_value(diagnostic, "code", severity))
        by_horizon.setdefault(HorizonId(raw_id), []).append(code)
    return {horizon_id: tuple(sorted(codes)) for horizon_id, codes in sorted(by_horizon.items(), key=lambda item: item[0].number)}


def _active_locks_by_horizon(locks: Any, *, now: datetime | str | None) -> dict[HorizonId, tuple[str, ...]]:
    rows = _extract_sequence(locks, ("locks", "active_locks", "records", "claims"))
    active: dict[HorizonId, list[str]] = {}
    now_dt = _parse_time(now)
    for lock in rows:
        status = _text_value(_get_value(lock, "status", "active")).lower()
        if status and status not in ACTIVE_LOCK_STATUSES:
            continue
        expires_at = _get_value(lock, "expires_at", None)
        if expires_at and now_dt and _parse_time(expires_at) and _parse_time(expires_at) <= now_dt:
            continue
        raw_id = _get_value(lock, "horizon_id", None) or _get_value(lock, "id", None)
        if raw_id is None:
            continue
        agent = _text_value(_get_value(lock, "agent_id", "unknown-agent"))
        active.setdefault(HorizonId(raw_id), []).append(agent)
    return {horizon_id: tuple(sorted(agents)) for horizon_id, agents in sorted(active.items(), key=lambda item: item[0].number)}


def _extract_sequence(source: Any, names: tuple[str, ...]) -> tuple[Any, ...]:
    if source is None:
        return ()
    if isinstance(source, dict):
        for name in names:
            value = source.get(name)
            if isinstance(value, (list, tuple)):
                return tuple(value)
        if all(key in source for key in ("horizon_id", "status")):
            return (source,)
        return ()
    for name in names:
        value = getattr(source, name, None)
        if isinstance(value, (list, tuple)):
            return tuple(value)
    if isinstance(source, (list, tuple)):
        return tuple(source)
    return ()


def _get_value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _text_value(value: Any) -> str:
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _dependency_depths(state: HorizonState) -> dict[HorizonId, int]:
    records = {record.id: record for record in state.records}
    memo: dict[HorizonId, int] = {}

    def depth(horizon_id: HorizonId, seen: frozenset[HorizonId] = frozenset()) -> int:
        if horizon_id in memo:
            return memo[horizon_id]
        if horizon_id in seen or horizon_id not in records:
            return 0
        deps = [dependency.id for dependency in records[horizon_id].dependencies if dependency.id in records]
        value = 0 if not deps else 1 + max(depth(dep, seen | {horizon_id}) for dep in deps)
        memo[horizon_id] = value
        return value

    for record in state.records:
        depth(record.id)
    return memo


def _format_time(value: datetime | str | None) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
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


def _round(value: float) -> float:
    return round(float(value), 4)
