"""Verification tests for H52 watcher contracts."""

from pathlib import Path

from horizon_manager.events import read_events
from horizon_manager.watch import (
    SnapshotWatchBackend,
    WatchConfig,
    WatchEvent,
    classify_change,
    daemon_refresh_commands,
    debounce_events,
    plan_refresh,
    run_watch_loop,
    snapshot_watch_paths,
)


def test_readme_change_refreshes_all_horizon_views() -> None:
    plan = classify_change("management/x/horizons/H51_Horizon_Manager_Daemon/README.md")
    assert plan.refresh_state is True
    assert plan.refresh_dashboard is True
    assert plan.refresh_dag is True
    assert plan.refresh_history is True
    assert plan.targets == ("state", "dashboard", "dag", "history")


def test_horizon_validation_doc_change_refreshes_all_horizon_views() -> None:
    plan = classify_change("management/x/horizons/H52_Horizon_File_Watcher/V_03_Implementation_Evidence.md")
    assert plan.targets == ("state", "dashboard", "dag", "history")
    assert plan.reasons == ("horizon-document",)


def test_horizonts_alias_doc_change_refreshes_all_horizon_views() -> None:
    plan = classify_change("management/horizonts/H52_Horizon_File_Watcher/README.md")
    assert plan.targets == ("state", "dashboard", "dag", "history")
    assert plan.reasons == ("horizon-document",)


def test_git_status_change_refreshes_preflight_only() -> None:
    plan = classify_change("git-status")
    assert plan.refresh_preflight is True
    assert plan.refresh_state is False
    assert plan.targets == ("preflight",)


def test_generated_render_outputs_do_not_recurse() -> None:
    dashboard = classify_change("management/subprojects/hermes-consistency-orchestrator/horizon_dashboard.html")
    dag = classify_change("management/subprojects/hermes-consistency-orchestrator/horizon_dependency_graph.html")
    assert dashboard.targets == ()
    assert dashboard.reasons == ("render-output",)
    assert dag.targets == ()
    assert dag.reasons == ("render-output",)


def test_debounce_keeps_last_event_per_path_per_window() -> None:
    events = [
        WatchEvent(Path("a/README.md"), "modified", 0),
        WatchEvent(Path("a/README.md"), "modified", 50),
        WatchEvent(Path("b/horizon_locks.json"), "modified", 60),
        WatchEvent(Path("a/README.md"), "modified", 220),
    ]
    debounced = debounce_events(events, 100)
    assert [event.timestamp_ms for event in debounced] == [50, 60, 220]


def test_plan_refresh_is_deterministic_for_same_event_sequence() -> None:
    events = [
        WatchEvent(Path("git-status"), "modified", 20, "git"),
        WatchEvent(Path("management/x/horizons/H52_Horizon_File_Watcher/README.md"), "modified", 10, "fs"),
        WatchEvent(Path("horizon_events.jsonl"), "modified", 30, "fs"),
    ]
    first = plan_refresh(events, window_ms=250)
    second = plan_refresh(list(reversed(events)), window_ms=250)
    assert first.to_dict() == second.to_dict()
    assert first.targets == ("state", "dashboard", "dag", "history", "preflight")
    assert first.event_count == 3


def test_daemon_refresh_commands_are_deterministic() -> None:
    request = plan_refresh(
        [
            WatchEvent(Path("management/x/horizons/H52_Horizon_File_Watcher/README.md"), "modified", 10),
            WatchEvent(Path("git-status"), "modified", 20),
        ]
    )
    commands = daemon_refresh_commands(
        request,
        WatchConfig(watched_roots=(Path("."),), daemon_endpoint="http://127.0.0.1:8765/"),
    )
    assert [command.to_dict() for command in commands] == [
        {"method": "GET", "payload": {}, "url": "http://127.0.0.1:8765/state"},
        {
            "method": "POST",
            "payload": request.to_dict(),
            "url": "http://127.0.0.1:8765/render",
        },
    ]


def test_run_watch_loop_uses_injectable_backend() -> None:
    class Backend:
        requested = None

        def events(self, config: WatchConfig) -> list[WatchEvent]:
            return [
                WatchEvent(Path("horizon_locks.json"), "modified", 10),
                WatchEvent(Path("git-status"), "modified", 20),
            ]

        def request_refresh(self, request):
            self.requested = request

    backend = Backend()
    plan = run_watch_loop(WatchConfig(watched_roots=(Path("."),)), backend)
    assert backend.requested == plan
    assert plan.refresh_dashboard is True
    assert plan.refresh_preflight is True


def test_run_watch_loop_records_refresh_event(tmp_path: Path) -> None:
    class Backend:
        requested = None

        def events(self, config: WatchConfig) -> list[WatchEvent]:
            return [WatchEvent(Path("management/x/horizons/H52_Horizon_File_Watcher/README.md"), "modified", 1000)]

        def request_refresh(self, request):
            self.requested = request

    event_log = tmp_path / "horizon_events.jsonl"
    backend = Backend()
    request = run_watch_loop(
        WatchConfig(watched_roots=(tmp_path,), event_log_path=event_log, actor="test-watch"),
        backend,
    )
    events = list(read_events(event_log))
    assert backend.requested == request
    assert len(events) == 1
    assert events[0].actor == "test-watch"
    assert events[0].event_type.value == "daemon"
    assert events[0].detail["targets"] == ["state", "dashboard", "dag", "history"]


def test_snapshot_backend_reports_changed_watched_files(tmp_path: Path) -> None:
    horizon = tmp_path / "management" / "horizons" / "H52_Horizon_File_Watcher"
    horizon.mkdir(parents=True)
    readme = horizon / "README.md"
    readme.write_text("# H52\n", encoding="utf-8")
    ignored = horizon / "notes.txt"
    ignored.write_text("ignored\n", encoding="utf-8")

    snapshot = snapshot_watch_paths((tmp_path,))
    assert str(readme).replace("\\", "/") in snapshot
    assert str(ignored).replace("\\", "/") not in snapshot

    backend = SnapshotWatchBackend(snapshot)
    readme.write_text("# H52\nupdated\n", encoding="utf-8")
    events = backend.events(WatchConfig(watched_roots=(tmp_path,)))
    assert [event.kind for event in events] == ["modified"]
    assert events[0].path == Path(str(readme))


if __name__ == "__main__":
    import tempfile

    test_readme_change_refreshes_all_horizon_views()
    test_horizon_validation_doc_change_refreshes_all_horizon_views()
    test_horizonts_alias_doc_change_refreshes_all_horizon_views()
    test_git_status_change_refreshes_preflight_only()
    test_generated_render_outputs_do_not_recurse()
    test_debounce_keeps_last_event_per_path_per_window()
    test_plan_refresh_is_deterministic_for_same_event_sequence()
    test_daemon_refresh_commands_are_deterministic()
    test_run_watch_loop_uses_injectable_backend()
    with tempfile.TemporaryDirectory() as raw:
        test_run_watch_loop_records_refresh_event(Path(raw))
    with tempfile.TemporaryDirectory() as raw:
        test_snapshot_backend_reports_changed_watched_files(Path(raw))
