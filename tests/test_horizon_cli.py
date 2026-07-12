"""Verification tests for H45 Horizon Manager CLI."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import tempfile

from horizon_manager.corpus import HorizonCorpus
from horizon_manager.cli import (
    CommandContext,
    CommandIO,
    CommandResult,
    ExitCode,
    build_parser,
    emit_result,
    run_command,
)


def test_parser_exposes_required_commands() -> None:
    parser = build_parser()
    subparsers = next(action for action in parser._actions if getattr(action, "dest", None) == "command")
    assert sorted(subparsers.choices) == [
        "claim",
        "conflicts",
        "corpora",
        "doctor",
        "events",
        "hook",
        "land",
        "next",
        "preflight",
        "release",
        "render",
        "state",
    ]


def test_json_output_is_deterministic() -> None:
    stdout = StringIO()
    result = CommandResult(True, "state", data={"z": 1, "a": {"b": 2}}, message="ok")
    emit_result(result, "json", CommandIO(stdout=stdout, stderr=StringIO()))

    payload = json.loads(stdout.getvalue())
    assert list(payload) == ["command", "data", "diagnostics", "exit_code", "message", "ok"]
    assert payload["data"] == {"a": {"b": 2}, "z": 1}
    assert payload["exit_code"] == 0


def test_text_output_uses_stderr_for_failures() -> None:
    stdout = StringIO()
    stderr = StringIO()
    result = CommandResult(False, "claim", message="claim rejected", exit_code=ExitCode.CONFLICT, diagnostics=("lock:H42",))
    emit_result(result, "text", CommandIO(stdout=stdout, stderr=stderr))

    assert stdout.getvalue() == ""
    assert "error: claim: claim rejected" in stderr.getvalue()
    assert "- lock:H42" in stderr.getvalue()


def test_text_output_includes_context_when_present() -> None:
    stdout = StringIO()
    result = CommandResult(True, "state", data={"context": {"corpus": "demo", "horizons_dir": "/tmp/horizons"}}, message="ok")
    emit_result(result, "text", CommandIO(stdout=stdout, stderr=StringIO()))

    assert "context: corpus=demo horizons_dir=/tmp/horizons" in stdout.getvalue()


def test_state_command_parses_temp_horizon_tree() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "horizons"
        _write_readme(horizons, "H39", "State", "implemented", 7, ())
        args = build_parser().parse_args(["--horizons-dir", str(horizons), "state"])

        result = run_command(args, context=CommandContext(repo_root=root, horizons_dir=horizons, generated_dir=root))

    assert result.ok is True
    assert result.data["horizon_count"] == 1
    assert result.data["context"]["corpus"] == "hco"
    assert result.data["context"]["horizons_dir"] == str(horizons)
    assert result.data["context"]["overrides"]["horizons_dir"] is True
    assert result.exit_code is ExitCode.SUCCESS


def test_command_context_records_selected_corpus_and_overrides() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "custom-horizons"
        generated = root / "custom-generated"
        generated.mkdir()
        _write_readme(horizons, "H01", "Alpha", "implemented", 1, ())
        args = build_parser().parse_args(
            [
                "--corpus",
                "horizon-manager",
                "--repo-root",
                str(root),
                "--horizons-dir",
                str(horizons),
                "--generated-dir",
                str(generated),
                "state",
            ]
        )

        result = run_command(args)

    context = result.data["context"]
    assert result.ok is True
    assert context == {
        "corpus": "horizon-manager",
        "generated_dir": str(generated),
        "horizons_dir": str(horizons),
        "overrides": {
            "generated_dir": True,
            "horizons_dir": True,
            "repo_root": True,
        },
        "repo_root": str(root),
    }


def test_corpora_command_lists_configured_external_corpora() -> None:
    args = build_parser().parse_args(["corpora"])

    result = run_command(args)

    assert result.ok is True
    assert result.data["action"] == "list"
    assert result.data["context"]["corpus"] == "hco"
    names = [row["name"] for row in result.data["corpora"]]
    assert names == ["hco", "cli-profile-manager", "geoforge", "horizon-manager"]
    assert all("horizon_count" in row for row in result.data["corpora"])
    assert all("healthy" in row for row in result.data["corpora"])


def test_corpora_list_action_is_explicit_alias() -> None:
    args = build_parser().parse_args(["corpora", "list"])

    result = run_command(args)

    assert result.ok is True
    assert result.data["action"] == "list"


def test_corpora_doctor_reports_healthy_temp_registry(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "management/horizons"
        _write_readme(horizons, "H01", "Alpha", "implemented", 1, ())
        corpus = HorizonCorpus("demo", "Demo", root, horizons, root / "management")
        monkeypatch.setattr("horizon_manager.cli.known_corpora", lambda: (corpus,))
        args = build_parser().parse_args(["corpora", "doctor"])

        result = run_command(args, context=CommandContext(repo_root=root, horizons_dir=horizons, generated_dir=root / "management"))

    assert result.ok is True
    assert result.message == "corpus registry healthy"
    assert result.data["action"] == "doctor"
    assert result.data["diagnostic_count"] == 0
    assert result.data["corpora"][0]["horizon_count"] == 1


def test_corpora_doctor_reports_path_diagnostics(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        missing = root / "missing"
        corpus = HorizonCorpus("missing", "Missing", missing, missing / "horizons", missing / "generated")
        monkeypatch.setattr("horizon_manager.cli.known_corpora", lambda: (corpus,))
        args = build_parser().parse_args(["corpora", "doctor"])

        result = run_command(args, context=CommandContext(repo_root=root, horizons_dir=root / "horizons", generated_dir=root))

    assert result.ok is False
    assert result.exit_code is ExitCode.VALIDATION_FAILURE
    assert result.message == "corpus registry diagnostics found"
    assert result.diagnostics == (
        "missing:generated_dir:missing_path",
        "missing:horizons_dir:missing_path",
        "missing:repo_root:missing_path",
    )
    assert result.data["diagnostic_count"] == 3


def test_corpus_selection_sets_context_paths() -> None:
    args = build_parser().parse_args(["--corpus", "cli-profile-manager", "state"])
    ctx = CommandContext(corpus_name=args.corpus)

    assert ctx.horizons_dir.as_posix().endswith("cli-profile-manager/management/horizons")
    assert ctx.generated_dir.as_posix().endswith("cli-profile-manager/management")


def test_claim_success_writes_lock_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "horizons"
        _write_readme(horizons, "H39", "State", "implemented", 7, ())
        _write_readme(horizons, "H41", "Conflicts", "implemented", 7, ())
        _write_readme(horizons, "H45", "CLI", "planned", 9, ("H39", "H41"))
        args = build_parser().parse_args(["--horizons-dir", str(horizons), "--generated-dir", str(root), "claim", "H45", "--agent", "agent-a", "--ttl", "60"])

        result = run_command(args, context=CommandContext(repo_root=root, horizons_dir=horizons, generated_dir=root, now="2026-07-11T10:00:00Z"))
        locks = json.loads((root / "horizon_locks.json").read_text(encoding="utf-8"))

    assert result.ok is True
    assert result.exit_code is ExitCode.SUCCESS
    assert locks["locks"][0]["horizon_id"] == "H45"
    assert locks["locks"][0]["agent_id"] == "agent-a"


def test_claim_conflict_maps_to_conflict_exit_code() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        horizons = root / "horizons"
        _write_readme(horizons, "H39", "State", "implemented", 7, ())
        _write_readme(horizons, "H41", "Conflicts", "implemented", 7, ())
        _write_readme(horizons, "H44", "Events", "planned", 8, ("H39",), owned_path="shared.py")
        _write_readme(horizons, "H45", "CLI", "planned", 9, ("H39", "H41"), owned_path="shared.py")
        parser = build_parser()
        ctx = CommandContext(repo_root=root, horizons_dir=horizons, generated_dir=root, now="2026-07-11T10:00:00Z")

        first = run_command(parser.parse_args(["--horizons-dir", str(horizons), "--generated-dir", str(root), "claim", "H44", "--agent", "agent-a"]), context=ctx)
        second = run_command(parser.parse_args(["--horizons-dir", str(horizons), "--generated-dir", str(root), "claim", "H45", "--agent", "agent-b"]), context=ctx)

    assert first.ok is True
    assert second.ok is False
    assert second.exit_code is ExitCode.CONFLICT
    assert "conflict:H44" in second.diagnostics


def test_release_missing_claim_maps_to_missing_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = build_parser().parse_args(["--generated-dir", str(root), "release", "H45", "--agent", "agent-a"])

        result = run_command(args, context=CommandContext(repo_root=root, horizons_dir=root / "horizons", generated_dir=root))

    assert result.ok is False
    assert result.exit_code is ExitCode.MISSING_CLAIM
    assert result.diagnostics == ("not_active:H45",)


def test_events_command_reads_jsonl_tail() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "horizon_events.jsonl").write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")
        args = build_parser().parse_args(["--generated-dir", str(root), "events", "--tail", "1"])

        result = run_command(args, context=CommandContext(repo_root=root, generated_dir=root))

    assert result.ok is True
    assert result.data["event_count"] == 2
    assert result.data["events"] == [{"id": 2}]
    assert result.data["context"]["generated_dir"] == str(root)


def test_delegated_commands_return_validation_failure_until_modules_land() -> None:
    args = build_parser().parse_args(["preflight"])
    result = run_command(args, context=CommandContext(repo_root=Path(".")))

    assert result.ok is False
    assert result.exit_code is ExitCode.VALIDATION_FAILURE
    assert result.diagnostics == ("delegate_not_ready:H46",)


def test_bad_command_returns_invocation_failure_without_parser() -> None:
    class Args:
        command = "missing"

    result = run_command(Args(), context=CommandContext(repo_root=Path(".")))

    assert result.ok is False
    assert result.exit_code is ExitCode.BAD_INVOCATION


def _write_readme(
    root: Path,
    horizon: str,
    title: str,
    status: str,
    wave: int,
    deps: tuple[str, ...],
    *,
    owned_path: str | None = None,
) -> None:
    path = root / f"{horizon}_{title.replace(' ', '_')}" / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    dep_text = "" if not deps else "after " + "/".join(deps)
    owned = owned_path or f"management/subprojects/horizon-manager/{horizon.lower()}.py"
    path.write_text(
        f"""# HCO-{horizon} {title}

Status: {status} (Wave {wave}{', ' + dep_text if dep_text else ''}).

## Purpose
Test fixture.

## Owned Files (EXCLUSIVE)
- `{owned}`

## Concurrency
Wave {wave}{', ' + dep_text if dep_text else ''}.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    test_parser_exposes_required_commands()
    test_json_output_is_deterministic()
    test_text_output_uses_stderr_for_failures()
    test_text_output_includes_context_when_present()
    test_state_command_parses_temp_horizon_tree()
    test_command_context_records_selected_corpus_and_overrides()
    test_corpora_command_lists_configured_external_corpora()
    test_corpora_list_action_is_explicit_alias()
    test_corpus_selection_sets_context_paths()
    test_claim_success_writes_lock_snapshot()
    test_claim_conflict_maps_to_conflict_exit_code()
    test_release_missing_claim_maps_to_missing_claim()
    test_events_command_reads_jsonl_tail()
    test_delegated_commands_return_validation_failure_until_modules_land()
    test_bad_command_returns_invocation_failure_without_parser()
