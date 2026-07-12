"""Verification tests for H53 hook contracts."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.cli import ExitCode, build_parser, run_command, CommandContext  # noqa: E402
from horizon_manager.hooks import (
    HookContext,
    HookMode,
    classify_hook_change,
    render_hook_report,
    run_hook,
)  # noqa: E402
from horizon_manager.model import HorizonRecord, HorizonState, HorizonStatus, OwnedPath, OwnedPathMode  # noqa: E402


def test_hook_classifies_horizon_owned_file() -> None:
    path = "management/x/horizons/H53_Horizon_Hooks_Integration/README.md"
    assert classify_hook_change(path) == "horizon-owned"


def test_hook_classifies_horizonts_alias_file() -> None:
    path = "management/horizonts/H53_Horizon_Hooks_Integration/README.md"
    context = HookContext(changed_paths=(Path(path),), claimed_horizons=("H53",))
    report = run_hook(HookMode.MANUAL, context)

    assert classify_hook_change(path) == "horizon-owned"
    assert report.ok is True
    assert report.horizon_ids == ("H53",)


def test_unclaimed_horizon_edit_blocks() -> None:
    context = HookContext(
        changed_paths=(Path("management/x/horizons/H53_Horizon_Hooks_Integration/README.md"),),
        claimed_horizons=(),
    )
    report = run_hook(HookMode.PRE_COMMIT, context)
    assert report.ok is False
    assert report.horizon_ids == ("H53",)
    assert "unclaimed horizon edits: H53" in report.diagnostics


def test_foreign_owned_file_edit_blocks_from_state() -> None:
    context = HookContext(
        changed_paths=(Path("management/subprojects/horizon-manager/src/horizon_manager/locks.py"),),
        claimed_horizons=("H53",),
        state=_state(),
    )
    report = run_hook(HookMode.PRE_COMMIT, context)
    assert report.ok is False
    assert report.horizon_ids == ("H42",)
    assert "foreign owned-file changes: management/subprojects/horizon-manager/src/horizon_manager/locks.py" in report.diagnostics


def test_stale_inventory_is_reported_separately() -> None:
    context = HookContext(
        changed_paths=(
            Path("MANAGEMENT_DOC_INVENTORY.md"),
            Path("management/x/horizons/H53_Horizon_Hooks_Integration/README.md"),
        ),
        claimed_horizons=("H53",),
    )
    report = run_hook(HookMode.MANUAL, context)
    assert report.ok is False
    assert "stale inventory: inventory churn must be regenerated after horizon edits" in report.diagnostics


def test_inventory_only_can_pass() -> None:
    report = run_hook(HookMode.PRE_COMMIT, HookContext(changed_paths=(Path("MANAGEMENT_DOC_INVENTORY.md"),)))
    assert report.ok is True
    assert report.diagnostics == ()


def test_claimed_horizon_edit_passes() -> None:
    context = HookContext(
        changed_paths=(Path("management/x/horizons/H53_Horizon_Hooks_Integration/README.md"),),
        claimed_horizons=("H53",),
    )
    report = run_hook("pre_push", context)
    assert report.ok is True
    assert "ok" in render_hook_report(report)


def test_reports_serialize_deterministic_json_and_text() -> None:
    context = HookContext(
        changed_paths=(
            Path("management/x/horizons/H53_Horizon_Hooks_Integration/README.md"),
            Path("MANAGEMENT_DOC_INVENTORY.md"),
        ),
        claimed_horizons=(),
    )
    report = run_hook("manual", context)
    first = render_hook_report(report, "json")
    second = render_hook_report(report, "json")
    payload = json.loads(first)

    assert first == second
    assert list(payload) == ["bypass_guidance", "changed_paths", "changes", "diagnostics", "horizon_ids", "mode", "ok"]
    assert render_hook_report(report).startswith("horizon hook manual: blocked")
    assert "Next action:" in render_hook_report(report)


def test_cli_exposes_hook_command_and_maps_failure_exit_code() -> None:
    parser = build_parser()
    subparsers = next(action for action in parser._actions if getattr(action, "dest", None) == "command")
    assert "hook" in subparsers.choices

    args = parser.parse_args(
        [
            "--horizons-dir",
            "management/subprojects/hermes-consistency-orchestrator/horizons",
            "--generated-dir",
            "management/subprojects/hermes-consistency-orchestrator",
            "hook",
            "--mode",
            "manual",
            "--changed-path",
            "management/subprojects/hermes-consistency-orchestrator/horizons/H53_Horizon_Hooks_Integration/README.md",
        ]
    )
    result = run_command(args, context=CommandContext(repo_root=ROOT))
    assert result.ok is False
    assert result.exit_code is ExitCode.VALIDATION_FAILURE
    assert "unclaimed horizon edits: H53" in result.diagnostics


def _state() -> HorizonState:
    return HorizonState(
        (
            HorizonRecord(
                id="H42",
                title="Horizon Locks",
                directory="horizons/H42",
                source_path="horizons/H42/README.md",
                status=HorizonStatus.IMPLEMENTED,
                owned_files=(
                    OwnedPath("management/subprojects/horizon-manager/src/horizon_manager/locks.py", OwnedPathMode.EXCLUSIVE),
                ),
            ),
            HorizonRecord(
                id="H53",
                title="Horizon Hooks Integration",
                directory="horizons/H53",
                source_path="horizons/H53/README.md",
                status=HorizonStatus.PLANNED,
                owned_files=(
                    OwnedPath("management/subprojects/horizon-manager/src/horizon_manager/hooks.py", OwnedPathMode.EXCLUSIVE),
                ),
            ),
        )
    )


if __name__ == "__main__":
    test_hook_classifies_horizon_owned_file()
    test_unclaimed_horizon_edit_blocks()
    test_foreign_owned_file_edit_blocks_from_state()
    test_stale_inventory_is_reported_separately()
    test_inventory_only_can_pass()
    test_claimed_horizon_edit_passes()
    test_reports_serialize_deterministic_json_and_text()
    test_cli_exposes_hook_command_and_maps_failure_exit_code()
