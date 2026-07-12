"""Verification tests for H42 horizon locks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile

from horizon_manager.conflicts import build_conflict_matrix
from horizon_manager.locks import (
    HorizonLock,
    LockSnapshot,
    LockStatus,
    LockStore,
    claim_horizon,
    prune_stale_locks,
    release_horizon,
    status_for_horizon,
)
from horizon_manager.model import (
    HorizonDependency,
    HorizonId,
    HorizonRecord,
    HorizonState,
    HorizonStatus,
    OwnedPath,
    OwnedPathMode,
)


NOW = datetime(2026, 7, 11, 9, 30, tzinfo=UTC)


def test_successful_claim_records_owner_paths_and_ttl() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, "state.py"),
        _record("H41", "Conflicts", HorizonStatus.IMPLEMENTED, "conflicts.py", deps=("H39",)),
        _record("H42", "Locks", HorizonStatus.PLANNED, "locks.py", deps=("H39", "H41")),
    )
    snapshot, decision = claim_horizon(state, build_conflict_matrix(state), LockSnapshot(), "H42", "agent-a", 900, now=NOW)

    assert decision.ok is True
    assert decision.lock is not None
    assert decision.lock.horizon_id == HorizonId("H42")
    assert decision.lock.agent_id == "agent-a"
    assert decision.lock.status is LockStatus.ACTIVE
    assert decision.lock.claimed_paths == ("locks.py",)
    assert decision.lock.claimed_at == "2026-07-11T09:30:00Z"
    assert decision.lock.expires_at == "2026-07-11T09:45:00Z"
    assert decision.lock.ttl_seconds == 900
    assert snapshot.status_counts()["active"] == 1


def test_claim_rejects_missing_dependencies_with_history() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.PLANNED, "state.py"),
        _record("H42", "Locks", HorizonStatus.PLANNED, "locks.py", deps=("H39",)),
    )
    snapshot, decision = claim_horizon(state, None, None, "H42", "agent-a", now=NOW)

    assert decision.ok is False
    assert "dependency:H39" in decision.blockers
    assert snapshot.locks[0].status is LockStatus.REJECTED
    assert snapshot.locks[0].reason == "dependency:H39"


def test_claim_rejects_conflicting_active_lock_with_evidence() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, "state.py"),
        _record("H41", "Conflicts", HorizonStatus.IMPLEMENTED, "conflicts.py"),
        _record("H42", "Locks", HorizonStatus.PLANNED, "shared.py", deps=("H39", "H41")),
        _record("H43", "Next", HorizonStatus.PLANNED, "shared.py", deps=("H42",)),
    )
    conflicts = build_conflict_matrix(state)
    locked, first = claim_horizon(state, conflicts, None, "H42", "agent-a", now=NOW)
    rejected, second = claim_horizon(state, conflicts, locked, "H43", "agent-b", now=NOW)

    assert first.ok is True
    assert second.ok is False
    assert "conflict:H42" in second.blockers
    rejected_lock = rejected.status_for_horizon("H43")[0]
    assert rejected_lock.status is LockStatus.REJECTED
    assert rejected_lock.conflicts[0].horizon_id == HorizonId("H42")
    assert rejected_lock.conflicts[0].paths == ("shared.py",)


def test_reclaim_by_same_agent_is_idempotent() -> None:
    state = _state(_record("H42", "Locks", HorizonStatus.PLANNED, "locks.py"))
    snapshot, first = claim_horizon(state, None, None, "H42", "agent-a", now=NOW)
    again, second = claim_horizon(state, None, snapshot, "H42", "agent-a", now=NOW + timedelta(minutes=1))

    assert first.ok is True
    assert second.ok is True
    assert second.lock == first.lock
    assert again.to_json() == snapshot.to_json()


def test_release_requires_owner_and_preserves_history() -> None:
    state = _state(_record("H42", "Locks", HorizonStatus.PLANNED, "locks.py"))
    snapshot, _decision = claim_horizon(state, None, None, "H42", "agent-a", now=NOW)

    blocked_snapshot, blocked = release_horizon(snapshot, "H42", "agent-b", now=NOW)
    released_snapshot, released = release_horizon(blocked_snapshot, "H42", "agent-a", now=NOW + timedelta(minutes=5))

    assert blocked.ok is False
    assert blocked.blockers == ("owner:agent-a",)
    assert released.ok is True
    assert released.lock is not None
    assert released.lock.status is LockStatus.RELEASED
    assert released.lock.released_at == "2026-07-11T09:35:00Z"
    assert released_snapshot.status_counts()["released"] == 1


def test_prune_stale_locks_marks_expired_without_deleting() -> None:
    lock = HorizonLock(
        "H42",
        "agent-a",
        claimed_at="2026-07-11T08:00:00Z",
        expires_at="2026-07-11T08:30:00Z",
        ttl_seconds=1800,
        claimed_paths=("locks.py",),
    )
    snapshot = prune_stale_locks(LockSnapshot((lock,)), now=NOW)

    assert len(snapshot.locks) == 1
    assert snapshot.locks[0].status is LockStatus.STALE
    assert snapshot.locks[0].reason == "ttl expired"


def test_snapshot_json_and_store_are_deterministic() -> None:
    later = HorizonLock("H43", "agent-b", claimed_at="2026-07-11T09:31:00Z", claimed_paths=("b.py",))
    earlier = HorizonLock("H42", "agent-a", claimed_at="2026-07-11T09:30:00Z", claimed_paths=("a.py",))
    snapshot = LockSnapshot((later, earlier), generated_at="2026-07-11T09:32:00Z", metadata={"z": 1, "a": 2})

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "horizon_locks.json"
        store = LockStore(path)
        store.save(snapshot)
        loaded = store.load()
        store.save(loaded)
        first = path.read_text(encoding="utf-8")
        store.save(loaded)
        second = path.read_text(encoding="utf-8")

    assert first == second
    assert loaded.locks[0].horizon_id == HorizonId("H42")
    assert loaded.to_dict()["metadata"] == {"a": 2, "z": 1}


def test_status_for_horizon_accepts_dict_shape_used_by_next_engine() -> None:
    rows = {"locks": [{"horizon_id": "H42", "agent_id": "agent-a", "status": "claimed"}]}
    history = status_for_horizon(rows, "H42")

    assert len(history) == 1
    assert history[0].status is LockStatus.ACTIVE

def _record(
    horizon_id: str,
    title: str,
    status: HorizonStatus,
    path: str,
    *,
    deps: tuple[str, ...] = (),
) -> HorizonRecord:
    return HorizonRecord(
        id=HorizonId(horizon_id),
        title=title,
        directory=f"horizons/{horizon_id}",
        source_path=f"horizons/{horizon_id}/README.md",
        status=status,
        wave=8,
        dependencies=tuple(HorizonDependency(HorizonId(dep), "test") for dep in deps),
        owned_files=(OwnedPath(path, OwnedPathMode.EXCLUSIVE),),
    )


def _state(*records: HorizonRecord) -> HorizonState:
    return HorizonState(tuple(records), generated_from="test")


if __name__ == "__main__":
    test_successful_claim_records_owner_paths_and_ttl()
    test_claim_rejects_missing_dependencies_with_history()
    test_claim_rejects_conflicting_active_lock_with_evidence()
    test_reclaim_by_same_agent_is_idempotent()
    test_release_requires_owner_and_preserves_history()
    test_prune_stale_locks_marks_expired_without_deleting()
    test_snapshot_json_and_store_are_deterministic()
    test_status_for_horizon_accepts_dict_shape_used_by_next_engine()
