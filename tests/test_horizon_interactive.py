"""Tests for the keyboard-first Horizon Manager console."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager import cli  # noqa: E402
from horizon_manager.cli import CommandContext, CommandResult  # noqa: E402
from horizon_manager.interactive import _compact_path, _default_menu_runner, command_feedback_lines, operator_status_lines, render_menu_lines, run_interactive_main  # noqa: E402


def test_menu_lines_match_keyboard_first_surface() -> None:
    lines = render_menu_lines(("[1] Overview", "[x] Exit"), "HORIZON MANAGER", selected_idx=0)

    text = "\n".join(lines)
    assert "HORIZON MANAGER" in text
    assert "Actions" in text
    assert "▌" in text
    assert "[1] Overview" in text
    assert "digits/shortcuts" in text
    assert "Esc/q" in text
    assert "\033[48;5;0m" in text


def test_interactive_main_can_exit_from_selector() -> None:
    result = run_interactive_main(CommandContext(repo_root=ROOT), menu_runner=lambda options, context, title: 8)

    assert result == 0


def test_default_menu_runner_shows_active_corpus(monkeypatch, capsys) -> None:
    monkeypatch.setattr("horizon_manager.interactive.run_menu", lambda options, title, shortcuts, pre_lines: print("\n".join(pre_lines)) or 8)

    selected = _default_menu_runner(("[x] Exit",), CommandContext(corpus_name="horizon-manager"))

    output = capsys.readouterr().out
    assert selected == 8
    assert "Corpus:" in output
    assert "horizon-manager" in output
    assert "Horizons:" in output
    assert "Locks:" in output
    assert "active=" in output
    assert "Doctor:" in output
    assert "Worktree:" in output
    assert "Next:" in output
    assert "management/horizons" in output


def test_operator_status_lines_are_script_friendly(monkeypatch) -> None:
    monkeypatch.setattr("horizon_manager.interactive._dirty_status", lambda context: "clean")

    lines = operator_status_lines(CommandContext(corpus_name="horizon-manager"))

    assert all("\n" not in line for line in lines)
    assert any("Corpus:" in line and "horizon-manager" in line for line in lines)
    assert any("Worktree:" in line and "clean" in line for line in lines)
    assert any("Next:" in line and "Hook Check" in line for line in lines)


def test_compact_path_preserves_tail_for_long_horizon_paths() -> None:
    path = "/home/olivercromwell/projects/shared/GeoForge/management/subprojects/hermes-consistency-orchestrator/horizons"

    compact = _compact_path(path, max_width=48)

    assert len(compact) <= 48
    assert compact.endswith("hermes-consistency-orchestrator/horizons")
    assert "..." in compact


def test_command_feedback_summarizes_doctor_hook_and_preflight() -> None:
    doctor = CommandResult(
        False,
        "doctor",
        data={"diagnostics": [{"severity": "error"}], "severity_counts": {"error": 1, "warn": 0}},
        message="diagnostics found errors",
    )
    hook = CommandResult(
        False,
        "hook",
        data={"report": {"changes": [{"classification": "horizon-owned"}], "diagnostics": ["blocked"], "ok": False}},
        message="hook checks blocked",
    )
    preflight = CommandResult(
        True,
        "preflight",
        data={"report": {"checks": [{"status": "pass"}], "blockers": [], "ok": True}},
        message="preflight checks passed",
    )

    assert command_feedback_lines(doctor) == ("summary: doctor blocked; diagnostics=1 errors=1 warnings=0",)
    assert command_feedback_lines(hook) == ("summary: hook blocked; changed=1 diagnostics=1 classifications=horizon-owned=1",)
    assert command_feedback_lines(preflight) == ("summary: preflight ok; checks=1 blockers=0 statuses=pass=1",)


def test_interactive_corpus_selector_changes_context(monkeypatch, capsys) -> None:
    selections = iter([0, 3, 1, 8])
    direct_calls = []

    def choose(options, context, title):
        return next(selections)

    def fake_direct(argv, context):
        direct_calls.append((tuple(argv), context.corpus_name))
        return 0

    monkeypatch.setattr("horizon_manager.interactive._run_direct", fake_direct)
    monkeypatch.setattr("horizon_manager.interactive._pause", lambda: None)

    result = run_interactive_main(CommandContext(corpus_name="hco"), menu_runner=choose)

    assert result == 0
    assert ("Selected corpus: horizon-manager" in capsys.readouterr().out)
    assert direct_calls == [(("next", "--limit", "8"), "horizon-manager")]


def test_interactive_help_returns_to_loop(monkeypatch, capsys) -> None:
    selections = iter([7, 8])
    pauses = []

    monkeypatch.setattr("horizon_manager.interactive._pause", lambda: pauses.append("pause"))

    result = run_interactive_main(CommandContext(corpus_name="horizon-manager"), menu_runner=lambda options, context, title: next(selections))

    output = capsys.readouterr().out
    assert result == 0
    assert "External Horizon Manager command surface" in output
    assert pauses == ["pause"]


def test_interactive_hook_check_delegates_to_cli_without_explicit_claim(monkeypatch) -> None:
    selections = iter([6, 8])
    direct_calls = []

    monkeypatch.setattr("horizon_manager.interactive._run_direct", lambda argv, context: direct_calls.append((tuple(argv), context.corpus_name)) or 0)
    monkeypatch.setattr("horizon_manager.interactive._pause", lambda: None)

    result = run_interactive_main(CommandContext(corpus_name="horizon-manager"), menu_runner=lambda options, context, title: next(selections))

    assert result == 0
    assert direct_calls == [(("hook", "--mode", "manual"), "horizon-manager")]


def test_cli_main_without_args_delegates_to_interactive(monkeypatch=None) -> None:
    calls = []

    def fake_interactive() -> int:
        calls.append("interactive")
        return 0

    original = sys.modules.pop("horizon_manager.interactive", None)
    try:
        import types

        module = types.ModuleType("horizon_manager.interactive")
        module.run_interactive_main = fake_interactive
        sys.modules["horizon_manager.interactive"] = module
        assert cli.main([]) == 0
    finally:
        if original is None:
            sys.modules.pop("horizon_manager.interactive", None)
        else:
            sys.modules["horizon_manager.interactive"] = original

    assert calls == ["interactive"]


if __name__ == "__main__":
    test_menu_lines_match_keyboard_first_surface()
    test_interactive_main_can_exit_from_selector()
    test_interactive_hook_check_delegates_to_cli_without_explicit_claim()
    test_cli_main_without_args_delegates_to_interactive()
