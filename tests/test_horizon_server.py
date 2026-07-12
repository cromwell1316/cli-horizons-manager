"""Verification tests for H51 daemon contracts."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from horizon_manager.locks import HorizonLock, LockSnapshot, LockStatus
from horizon_manager.model import HorizonDependency, HorizonRecord, HorizonState, HorizonStatus, OwnedPath, OwnedPathMode
from horizon_manager.server import DaemonConfig, DaemonRequest, DaemonState, handle_request, refresh_state


def test_state_endpoint_returns_stable_envelope() -> None:
    state = DaemonState(data={"state": {"horizons": 53}}, diagnostics=["missing:locks"])
    response = handle_request(DaemonRequest("GET", "/state"), state)
    assert response == {"ok": True, "data": {"horizons": 53}, "diagnostics": ["missing:locks"], "error": None}


def test_all_read_endpoints_exist() -> None:
    state = DaemonState(
        data={
            "metadata": {"corpus": "demo"},
            "state": {"count": 1},
            "doctor": {"ok": True},
            "conflicts": {"conflict_count": 0},
            "locks": {"locks": []},
            "next": {"recommendations": []},
            "events": [],
            "dashboard": "<!doctype html>",
        }
    )
    for path in ("/metadata", "/state", "/doctor", "/conflicts", "/locks", "/next", "/events", "/dashboard"):
        response = handle_request(DaemonRequest("GET", path), state)
        assert response["ok"] is True
        assert response["error"] is None


def test_refresh_state_exposes_corpus_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "management/horizons"
        generated = root / "management"
        _write_readme(horizons, "H39", "State", "implemented", 7, ())
        config = DaemonConfig(
            corpus_path=horizons,
            generated_dir=generated,
            corpus_name="demo",
            corpus_title="Demo Corpus",
            repo_root=root,
        )
        state = refresh_state(config)
        response = handle_request(DaemonRequest("GET", "/metadata"), state)

    assert response["ok"] is True
    assert response["data"] == {
        "corpus": "demo",
        "generated_dir": str(generated),
        "horizons_dir": str(horizons),
        "repo_root": str(root),
        "title": "Demo Corpus",
    }
    assert state.data["metadata"] == response["data"]


def test_readonly_blocks_mutations() -> None:
    state = _daemon_state()
    for path, payload in (
        ("/claim", {"horizon": "H51", "owner": "agent"}),
        ("/release", {"horizon": "H51", "owner": "agent"}),
        ("/render", {}),
    ):
        response = handle_request(DaemonRequest("POST", path, payload), state, readonly=True)
        assert response["ok"] is False
        assert "readonly" in response["error"]


def test_claim_conflict_is_deterministic_with_h42_locks() -> None:
    state = _daemon_state()
    first = handle_request(DaemonRequest("POST", "/claim", {"horizon": "H51", "owner": "agent-a"}), state, readonly=False)
    second = handle_request(DaemonRequest("POST", "/claim", {"horizon": "H51", "owner": "agent-b"}), state, readonly=False)

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["diagnostics"] == ["lock:agent-a"]
    assert state.data["locks"]["status_counts"]["active"] == 1


def test_release_uses_h42_owner_semantics() -> None:
    state = _daemon_state(
        locks=LockSnapshot(
            locks=(
                HorizonLock(
                    "H51",
                    "agent-a",
                    LockStatus.ACTIVE,
                    claimed_at="2026-07-11T12:00:00Z",
                    expires_at="2026-07-11T13:00:00Z",
                ),
            )
        )
    )
    bad = handle_request(DaemonRequest("POST", "/release", {"horizon": "H51", "owner": "agent-b"}), state, readonly=False)
    good = handle_request(DaemonRequest("POST", "/release", {"horizon": "H51", "owner": "agent-a"}), state, readonly=False)

    assert bad["ok"] is False
    assert bad["diagnostics"] == ["owner:agent-a"]
    assert good["ok"] is True
    assert state.data["locks"]["status_counts"]["released"] == 1


def test_refresh_state_reads_generated_files_and_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "horizons"
        _write_readme(horizons, "H39", "State", "implemented", 7, ())
        (root / "horizon_events.jsonl").write_text(
            json.dumps(
                {
                    "actor": "agent",
                    "correlation_id": "",
                    "detail": {},
                    "event_id": "e1",
                    "event_type": "note",
                    "horizon_id": "H39",
                    "message": "event",
                    "schema_version": 1,
                    "severity": "info",
                    "source": "test",
                    "ts": "2026-07-11T00:00:00Z",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        config = DaemonConfig(corpus_path=horizons, generated_dir=root)
        state = refresh_state(config)

    assert state.data["state"]["horizon_count"] == 1
    assert state.data["events"][0]["event_id"] == "e1"
    assert len(state.revision) == 64


def test_render_endpoint_writes_dashboard_and_dag() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state = _daemon_state(config=DaemonConfig(corpus_path=root / "horizons", generated_dir=root))
        response = handle_request(DaemonRequest("POST", "/render", {}), state, readonly=False)

        assert response["ok"] is True
        assert (root / "horizon_dashboard.html").exists()
        assert (root / "horizon_dependency_graph.html").exists()
        assert len(response["data"]["written"]) == 2


def test_config_rejects_non_localhost() -> None:
    try:
        DaemonConfig(Path("horizons"), Path("."), host="0.0.0.0").validate()
    except ValueError as exc:
        assert "localhost" in str(exc)
    else:
        raise AssertionError("non-localhost host accepted")


def _daemon_state(*, locks: LockSnapshot | None = None, config: DaemonConfig | None = None) -> DaemonState:
    state = DaemonState(config=config, horizon_state=_state(), lock_snapshot=locks or LockSnapshot())
    state.sync_data()
    return state


def _state() -> HorizonState:
    h39 = HorizonRecord(
        id="H39",
        title="State",
        directory="h/H39",
        source_path="h/H39/README.md",
        status=HorizonStatus.IMPLEMENTED,
        wave=7,
        concurrency="Wave 7.",
        owned_files=(OwnedPath("state.py", OwnedPathMode.EXCLUSIVE),),
    )
    h51 = HorizonRecord(
        id="H51",
        title="Daemon",
        directory="h/H51",
        source_path="h/H51/README.md",
        status=HorizonStatus.PLANNED,
        wave=11,
        concurrency="Wave 11 after H39.",
        dependencies=(HorizonDependency("H39", "after", "after H39"),),
        owned_files=(OwnedPath("server.py", OwnedPathMode.EXCLUSIVE),),
    )
    return HorizonState((h39, h51), generated_from="test")


def _write_readme(root: Path, horizon: str, title: str, status: str, wave: int, deps: tuple[str, ...]) -> None:
    path = root / f"{horizon}_{title}" / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    dep_text = "" if not deps else "after " + "/".join(deps)
    path.write_text(
        f"""# HCO-{horizon} {title}

Status: {status} (Wave {wave}{', ' + dep_text if dep_text else ''}).

## Purpose
Test fixture.

## Owned Files (EXCLUSIVE)
- `server.py`

## Concurrency
Wave {wave}{', ' + dep_text if dep_text else ''}.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    test_state_endpoint_returns_stable_envelope()
    test_all_read_endpoints_exist()
    test_readonly_blocks_mutations()
    test_claim_conflict_is_deterministic_with_h42_locks()
    test_release_uses_h42_owner_semantics()
    test_refresh_state_reads_generated_files_and_events()
    test_render_endpoint_writes_dashboard_and_dag()
    test_config_rejects_non_localhost()
