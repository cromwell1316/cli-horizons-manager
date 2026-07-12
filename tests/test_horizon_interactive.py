"""Tests for the keyboard-first Horizon Manager console."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager import cli  # noqa: E402
from horizon_manager.cli import CommandContext  # noqa: E402
from horizon_manager.interactive import render_menu_lines, run_interactive_main  # noqa: E402


def test_menu_lines_match_keyboard_first_surface() -> None:
    lines = render_menu_lines(("[1] Overview", "[x] Exit"), "HORIZON MANAGER", selected_idx=0)

    text = "\n".join(lines)
    assert "HORIZON MANAGER" in text
    assert "-->" in text
    assert "[1] Overview" in text
    assert "digits/shortcuts" in text
    assert "Esc/q" in text


def test_interactive_main_can_exit_from_selector() -> None:
    result = run_interactive_main(CommandContext(repo_root=ROOT), menu_runner=lambda options: 8)

    assert result == 0


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
