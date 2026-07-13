"""Tests for the keyboard-first Horizon Manager console."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager import cli  # noqa: E402
from horizon_manager.cli import CommandContext, CommandResult  # noqa: E402
from horizon_manager.interactive import OperatorSnapshot, _compact_path, _default_menu_runner, _pause, _run_direct, _show_command_result, command_feedback_lines, operator_status_lines, render_menu_lines, run_interactive_main, themed_block_lines  # noqa: E402

ANSI_RE = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


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


def test_themed_block_wraps_plain_lines_and_fills_terminal_width(monkeypatch) -> None:
    monkeypatch.setattr("horizon_manager.interactive.terminal_size", lambda fallback=(120, 30): (32, 10))

    lines = themed_block_lines(["alpha beta gamma delta epsilon zeta"], min_height=4, top_padding=0)
    plain_lines = [ANSI_RE.sub("", line) for line in lines]

    assert len(lines) == 4
    assert all(line.startswith("\033[48;5;0m") for line in lines)
    assert all(line.endswith("\033[0m") for line in lines)
    assert all(len(line) == 32 for line in plain_lines)


def test_pause_prompt_keeps_current_line_themed(monkeypatch) -> None:
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    _pause()

    assert prompts == ["\033[48;5;0m    \033[38;5;245mPress \033[37mEnter\033[38;5;245m to continue...\033[0m\033[48;5;0m\033[K"]


def test_interactive_main_can_exit_from_selector() -> None:
    result = run_interactive_main(CommandContext(repo_root=ROOT), menu_runner=lambda options, context, title: 8)

    assert result == 0


def test_default_menu_runner_shows_active_corpus(monkeypatch, capsys) -> None:
    monkeypatch.setattr("horizon_manager.interactive.run_menu", lambda options, title, shortcuts, pre_lines: print("\n".join(pre_lines)) or 8)
    monkeypatch.setattr(
        "horizon_manager.interactive._operator_snapshot",
        lambda context: OperatorSnapshot(
            corpus_name="horizon-manager",
            corpus_title="Horizon Manager",
            horizons_dir=str(ROOT / "management/subprojects/horizon-manager/management/horizons"),
            horizon_total=20,
            status_counts={"implemented": 18, "planned": 2},
            active_locks=0,
            total_locks=0,
            doctor_ok=True,
            diagnostics=0,
            worktree_dirty=0,
        ),
    )

    selected = _default_menu_runner(("[x] Exit",), CommandContext(corpus_name="horizon-manager"))

    output = capsys.readouterr().out
    plain = ANSI_RE.sub("", output)
    assert selected == 8
    assert "HORIZON-MANAGER Mission Control" in plain
    assert "Status:     READY TO CLAIM" in plain
    assert "READY TO CLAIM" in plain
    assert "Corpus:     " in plain
    assert "horizon-manager" in plain
    assert "State:      18 / 20 implemented | 2 planned | doctor ok | diag=0 | locks=0/0" in plain
    assert "Worktree:   clean; claim/release/hook available" in plain
    assert "Next:       Run Hook Check, then claim or continue the next planned horizon." in plain
    assert "management/horizons" not in plain


def test_operator_status_lines_prioritize_dirty_worktree_blocker(monkeypatch) -> None:
    monkeypatch.setattr(
        "horizon_manager.interactive._operator_snapshot",
        lambda context: OperatorSnapshot(
            corpus_name="hco",
            corpus_title="HCO subproject horizons",
            horizons_dir="/repo/management/subprojects/hermes-consistency-orchestrator/horizons",
            horizon_total=76,
            status_counts={"implemented": 74, "planned": 2},
            active_locks=0,
            total_locks=0,
            doctor_ok=True,
            diagnostics=0,
            worktree_dirty=33,
        ),
    )

    lines = operator_status_lines(CommandContext(corpus_name="hco"))
    plain_lines = [ANSI_RE.sub("", line) for line in lines]
    plain = "\n".join(plain_lines)

    assert all("\n" not in line for line in lines)
    assert len(lines) == 6
    assert "READY, BUT WORKTREE NEEDS REVIEW" in plain
    assert "74 / 76 implemented | 2 planned" in plain
    assert "doctor ok | diag=0 | locks=0/0" in plain
    assert "33 dirty path(s); claim/release/hook blocked" in plain
    assert "Review worktree changes; Refresh/Doctor stays available." in plain
    assert "Action Availability" not in plain


def test_operator_status_lines_show_doctor_blocker_before_actions(monkeypatch) -> None:
    monkeypatch.setattr(
        "horizon_manager.interactive._operator_snapshot",
        lambda context: OperatorSnapshot(
            corpus_name="hco",
            corpus_title="HCO subproject horizons",
            horizons_dir="/repo/horizons",
            horizon_total=76,
            status_counts={"implemented": 70, "planned": 5, "unknown": 1},
            active_locks=0,
            total_locks=0,
            doctor_ok=False,
            diagnostics=57,
            worktree_dirty=0,
        ),
    )

    plain = ANSI_RE.sub("", "\n".join(operator_status_lines(CommandContext(corpus_name="hco"))))

    assert "ACTIONS BLOCKED BY DOCTOR" in plain
    assert "70 / 76 implemented | 5 planned | 1 unknown" in plain
    assert "doctor diagnostics=57; claim/release/hook blocked" in plain
    assert "Open Doctor details and fix diagnostics." in plain


def test_operator_status_colons_are_attached_to_labels(monkeypatch) -> None:
    monkeypatch.setattr(
        "horizon_manager.interactive._operator_snapshot",
        lambda context: OperatorSnapshot(
            corpus_name="horizon-manager",
            corpus_title="Horizon Manager",
            horizons_dir="/repo/management/horizons",
            horizon_total=20,
            status_counts={"implemented": 18, "planned": 2},
            active_locks=0,
            total_locks=0,
            doctor_ok=True,
            diagnostics=0,
            worktree_dirty=0,
        ),
    )

    lines = [ANSI_RE.sub("", line) for line in operator_status_lines(CommandContext(corpus_name="horizon-manager"))]
    status_rows = [line for line in lines if ":" in line and line.split(":", 1)[0].strip() in {"Status", "Corpus", "State", "Worktree", "Next"}]
    value_columns = []
    for row in status_rows:
        label, rest = row.split(":", 1)
        value_columns.append(len(label) + 1 + len(rest) - len(rest.lstrip(" ")))

    assert status_rows
    assert all(line.split(":", 1)[0].endswith(" ") is False for line in status_rows)
    assert set(value_columns) == {12}


def test_render_menu_shortens_status_before_hiding_actions(monkeypatch) -> None:
    monkeypatch.setattr("horizon_manager.interactive.terminal_size", lambda fallback=(120, 30): (88, 14))

    lines = render_menu_lines(
        ("[0] Corpora", "[1] Overview", "[2] Refresh", "[3] Claim", "[4] Release", "[x] Exit"),
        "HORIZON MANAGER",
        selected_idx=0,
        pre_lines=tuple(f"status line {idx}" for idx in range(8)),
    )
    plain = ANSI_RE.sub("", "\n".join(lines))

    assert "[x] Exit" in plain
    assert "status shortened to keep actions visible" in plain
    assert "status line 7" not in plain


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
    assert command_feedback_lines(hook) == ("Status: blocked | Changed: 1 | Blocking: 1 | Horizon Owned: 1",)
    assert command_feedback_lines(preflight) == ("summary: preflight ok; checks=1 blockers=0 statuses=pass=1",)


def test_hook_result_screen_prioritizes_actions_and_changed_files(monkeypatch, capsys) -> None:
    monkeypatch.setattr("horizon_manager.interactive.terminal_size", lambda fallback=(120, 30): (100, 30))
    result = CommandResult(
        False,
        "hook",
        data={
            "context": {
                "corpus": "hco",
                "horizons_dir": "/home/olivercromwell/projects/shared/GeoForge/management/subprojects/hermes-consistency-orchestrator/horizons",
            },
            "report": {
                "bypass_guidance": "Next action: run `horizon-manager preflight`.",
                "changes": [
                    {
                        "classification": "detector-output",
                        "horizon_id": None,
                        "path": "management/subprojects/hermes-consistency-orchestrator/deep_audit/pool_state.json",
                        "status": "changed",
                    },
                    {
                        "classification": "horizon-owned",
                        "horizon_id": "H20",
                        "path": "management/subprojects/hermes-consistency-orchestrator/horizons/H20_Product_UX/README.md",
                        "status": "changed",
                    },
                ],
                "diagnostics": [
                    "deep-audit detector output is outside hook mutation scope: management/subprojects/hermes-consistency-orchestrator/deep_audit/pool_state.json",
                    "unclaimed horizon edits: H20",
                ],
                "horizon_ids": ["H20"],
                "ok": False,
            },
        },
        message="hook checks blocked",
        diagnostics=(
            "deep-audit detector output is outside hook mutation scope: management/subprojects/hermes-consistency-orchestrator/deep_audit/pool_state.json",
            "unclaimed horizon edits: H20",
        ),
    )

    _show_command_result(result)

    plain = ANSI_RE.sub("", capsys.readouterr().out)
    assert "Blocking Issues" in plain
    assert "Changed Files" in plain
    assert "detector-output:" in plain
    assert "horizon-owned H20:" in plain
    assert "Summary" in plain
    assert "Status: blocked | Changed: 2 | Blocking: 2 | Detector Output: 1 | Horizon Owned: 1" in plain
    assert "Claim affected horizon(s): H20." in plain
    assert "Move, accept, or revert detector output outside the hook mutation scope." in plain


def test_run_direct_uses_clean_command_screen(monkeypatch, capsys) -> None:
    calls = []

    monkeypatch.setattr("horizon_manager.interactive.clear_screen", lambda: calls.append("clear"))
    monkeypatch.setattr(
        "horizon_manager.interactive.run_command",
        lambda args, context: CommandResult(
            True,
            "next",
            data={"context": {"corpus": "horizon-manager", "horizons_dir": "/tmp/projects/shared/GeoForge/management/subprojects/horizon-manager/management/horizons"}},
            message="1 recommendations",
        ),
    )

    result = _run_direct(["next", "--limit", "1"], CommandContext(corpus_name="horizon-manager"))

    plain = ANSI_RE.sub("", capsys.readouterr().out)
    assert result == 0
    assert calls == ["clear"]
    assert "HORIZON MANAGER COMMAND" in plain
    assert "Command:    Overview / Next Horizons" in plain
    assert "Corpus:     horizon-manager" in plain
    assert "Result" in plain
    assert "Status:     ok" in plain
    assert "Message:    next: 1 recommendations" in plain
    assert "Context:    corpus=horizon-manager | horizons=" in plain
    assert "ok: next" not in plain


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
    themed_help_lines = [line for line in output.splitlines() if "External Horizon Manager command surface" in line or "positional arguments:" in line]
    assert result == 0
    assert "External Horizon Manager command surface" in output
    assert themed_help_lines
    assert all(line.startswith("\033[48;5;0m") for line in themed_help_lines)
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
    import pytest

    raise SystemExit(pytest.main([__file__]))
