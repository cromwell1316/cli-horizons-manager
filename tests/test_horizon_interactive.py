"""Tests for the keyboard-first Horizon Manager console."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager import cli  # noqa: E402
from horizon_manager.cli import CommandContext  # noqa: E402
from horizon_manager.interactive import _default_menu_runner, render_menu_lines, run_interactive_main  # noqa: E402


def test_menu_lines_match_keyboard_first_surface() -> None:
    lines = render_menu_lines(("[1] Overview", "[x] Exit"), "HORIZON MANAGER", selected_idx=0)

    text = "\n".join(lines)
    assert "HORIZON MANAGER" in text
    assert "-->" in text
    assert "[1] Overview" in text
    assert "digits/shortcuts" in text
    assert "Esc/q" in text


def test_interactive_main_can_exit_from_selector() -> None:
    result = run_interactive_main(CommandContext(repo_root=ROOT), menu_runner=lambda options, context, title: 8)

    assert result == 0


def test_default_menu_runner_shows_active_corpus(monkeypatch, capsys) -> None:
    monkeypatch.setattr("horizon_manager.interactive.run_menu", lambda options, title, shortcuts, pre_lines: print("\n".join(pre_lines)) or 8)

    selected = _default_menu_runner(("[x] Exit",), CommandContext(corpus_name="horizon-manager"))

    output = capsys.readouterr().out
    assert selected == 8
    assert "Active corpus: horizon-manager" in output
    assert "management/horizons" in output


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
    test_cli_main_without_args_delegates_to_interactive()
