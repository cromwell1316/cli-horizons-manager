"""Verification tests for H47 safe land gate."""

from __future__ import annotations

from dataclasses import dataclass

from horizon_manager.events import EventType
from horizon_manager.land import (
    GitResult,
    LandMode,
    LandPlan,
    build_land_plan,
    commit_message_for,
    execute_land_plan,
)


def test_dry_run_plan_serializes_allowed_and_rejected_paths() -> None:
    plan = build_land_plan(
        object(),
        "H47",
        "agent-a",
        LandMode.DRY_RUN,
        summary="safe land command",
        preflight_runner=lambda _h, _a: {
            "ok": True,
            "allowed_files": ["b.py", "a.py"],
            "rejected_files": ["foreign.py"],
            "diagnostics": ["foreign_file:foreign.py"],
        },
    )

    assert plan.safe is False
    assert plan.allowed_files == ("a.py", "b.py")
    assert plan.rejected_files == ("foreign.py",)
    assert plan.commands == ()
    assert plan.to_dict()["commit_message"] == "H47: safe land command"


def test_failed_preflight_prevents_all_git_mutation() -> None:
    plan = build_land_plan(
        object(),
        "H47",
        "agent-a",
        LandMode.COMMIT_AND_PUSH,
        preflight_runner=lambda _h, _a: {"ok": False, "allowed_files": ["a.py"], "diagnostics": ["claim_missing"]},
    )
    runner = FakeGitRunner()
    writer = FakeEventWriter()

    execution = execute_land_plan(plan, runner, writer)

    assert execution.ok is False
    assert execution.message == "preflight failed; no git commands executed"
    assert runner.calls == []
    assert writer.events[-1].event_type is EventType.LAND
    assert writer.events[-1].severity.value == "error"


def test_commit_only_stages_exact_allowed_paths_then_commits() -> None:
    plan = build_land_plan(
        object(),
        "H47",
        "agent-a",
        LandMode.COMMIT_ONLY,
        summary="implement land gate",
        preflight_runner=lambda _h, _a: {"ok": True, "allowed_files": ["src/land.py", "tests/test_land.py"]},
    )
    runner = FakeGitRunner()
    writer = FakeEventWriter()

    execution = execute_land_plan(plan, runner, writer)

    assert execution.ok is True
    assert runner.calls == [
        ("add", "--", "src/land.py"),
        ("add", "--", "tests/test_land.py"),
        ("commit", "-m", "H47: implement land gate"),
    ]
    assert all(call[:2] != ("add", ".") for call in runner.calls)
    assert [event.event_type for event in writer.events] == [EventType.COMMIT]


def test_commit_and_push_records_commit_and_push_events() -> None:
    plan = build_land_plan(
        object(),
        "H47",
        "agent-a",
        "commit_and_push",
        preflight_runner=lambda _h, _a: {"ok": True, "allowed_files": ["land.py"], "title": "land gate"},
    )
    writer = FakeEventWriter()

    execution = execute_land_plan(plan, FakeGitRunner(), writer)

    assert execution.ok is True
    assert [event.event_type for event in writer.events] == [EventType.COMMIT, EventType.PUSH]
    assert writer.events[-1].message == "push completed"


def test_push_failure_records_event_without_rewriting_history() -> None:
    plan = build_land_plan(
        object(),
        "H47",
        "agent-a",
        LandMode.COMMIT_AND_PUSH,
        preflight_runner=lambda _h, _a: {"ok": True, "allowed_files": ["land.py"]},
    )
    runner = FakeGitRunner(fail_on=("push", "origin", "HEAD:master"))
    writer = FakeEventWriter()

    execution = execute_land_plan(plan, runner, writer)

    assert execution.ok is False
    assert execution.message == "push failed"
    assert runner.calls[-1] == ("push", "origin", "HEAD:master")
    assert writer.events[-1].event_type is EventType.PUSH
    assert writer.events[-1].severity.value == "error"


def test_broad_staging_is_rejected_before_execution() -> None:
    for args in (("add", "."), ("add", "-A"), ("add", "--all")):
        try:
            LandPlan("H47", "agent-a", LandMode.COMMIT_ONLY, allowed_files=("safe.py",), commands=((args, "bad"),))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"broad staging command accepted: {args!r}")


def test_default_preflight_missing_fails_closed() -> None:
    plan = build_land_plan(object(), "H47", "agent-a", LandMode.COMMIT_ONLY)

    assert plan.safe is False
    assert "preflight_failed" in plan.diagnostics
    assert "preflight_runner_missing" in plan.diagnostics


def test_commit_message_is_deterministic() -> None:
    assert commit_message_for("h47", "  safe   land  ") == "H47: safe land"
    assert commit_message_for("H47", "H47: already formatted") == "H47: already formatted"
    assert commit_message_for("H47", "") == "H47: land horizon work"


@dataclass
class FakeGitRunner:
    fail_on: tuple[str, ...] | None = None
    calls: list[tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def run(self, args: tuple[str, ...]) -> GitResult:
        assert self.calls is not None
        call = tuple(args)
        self.calls.append(call)
        if self.fail_on == call:
            return GitResult(call, returncode=1, stderr="failed")
        return GitResult(call, stdout="ok")


@dataclass
class FakeEventWriter:
    events: list = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def write(self, event) -> None:
        self.events.append(event)


if __name__ == "__main__":
    test_dry_run_plan_serializes_allowed_and_rejected_paths()
    test_failed_preflight_prevents_all_git_mutation()
    test_commit_only_stages_exact_allowed_paths_then_commits()
    test_commit_and_push_records_commit_and_push_events()
    test_push_failure_records_event_without_rewriting_history()
    test_broad_staging_is_rejected_before_execution()
    test_default_preflight_missing_fails_closed()
    test_commit_message_is_deterministic()
