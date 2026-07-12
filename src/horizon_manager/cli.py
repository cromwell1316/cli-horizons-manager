"""Operator CLI for the Horizon Manager application."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import IntEnum
import json
from pathlib import Path
import sys
from typing import Any, Callable, TextIO

from .corpus import HorizonCorpus, corpus_names, default_corpus, known_corpora, resolve_corpus, validate_corpus_paths


class ExitCode(IntEnum):
    SUCCESS = 0
    BAD_INVOCATION = 2
    VALIDATION_FAILURE = 3
    CONFLICT = 4
    MISSING_CLAIM = 5
    INTERNAL_ERROR = 10


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    command: str
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    exit_code: ExitCode = ExitCode.SUCCESS
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.ok and self.exit_code is ExitCode.SUCCESS:
            object.__setattr__(self, "exit_code", ExitCode.VALIDATION_FAILURE)
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command,
            "exit_code": int(self.exit_code),
            "message": self.message,
            "diagnostics": list(self.diagnostics),
            "data": _stable_value(self.data),
        }


@dataclass(frozen=True)
class CommandIO:
    stdout: TextIO = sys.stdout
    stderr: TextIO = sys.stderr


@dataclass
class CommandContext:
    repo_root: Path | None = None
    corpus_name: str | None = None
    horizons_dir: Path | None = None
    generated_dir: Path | None = None
    now: str = ""
    corpus_title: str = field(init=False, default="")
    repo_root_overridden: bool = field(init=False, default=False)
    horizons_dir_overridden: bool = field(init=False, default=False)
    generated_dir_overridden: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        corpus = resolve_corpus(self.corpus_name)
        self.corpus_name = corpus.name
        self.corpus_title = corpus.title
        self.repo_root_overridden = self.repo_root is not None
        self.horizons_dir_overridden = self.horizons_dir is not None
        self.generated_dir_overridden = self.generated_dir is not None
        if self.repo_root is None:
            self.repo_root = corpus.repo_root
        else:
            self.repo_root = Path(self.repo_root)
        if self.horizons_dir is None:
            self.horizons_dir = corpus.horizons_dir
        else:
            self.horizons_dir = Path(self.horizons_dir)
        if self.generated_dir is None:
            self.generated_dir = corpus.generated_dir
        else:
            self.generated_dir = Path(self.generated_dir)

    def path(self, name: str) -> Path:
        assert self.generated_dir is not None
        return self.generated_dir / name

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus": str(self.corpus_name),
            "generated_dir": str(self.generated_dir),
            "horizons_dir": str(self.horizons_dir),
            "overrides": {
                "generated_dir": self.generated_dir_overridden,
                "horizons_dir": self.horizons_dir_overridden,
                "repo_root": self.repo_root_overridden,
            },
            "repo_root": str(self.repo_root),
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="horizon-manager", description="External Horizon Manager command surface.")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    parser.add_argument("--corpus", choices=corpus_names(), default=default_corpus().name, help="Managed horizon corpus.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the selected corpus root.")
    parser.add_argument("--horizons-dir", default=None, help="Override the selected corpus Horizon README directory.")
    parser.add_argument("--generated-dir", default=None, help="Override the selected corpus generated horizon_* artifact directory.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    corpora = subparsers.add_parser("corpora", help="Inspect configured horizon corpora.")
    corpora.add_argument("corpus_action", nargs="?", choices=("list", "doctor"), default="list", help="Registry action.")

    state = subparsers.add_parser("state", help="Parse horizon README state.")
    state.add_argument("--write", action="store_true", help="Write horizon_state.json.")

    doctor = subparsers.add_parser("doctor", help="Run horizon document diagnostics.")
    doctor.add_argument("--write", action="store_true", help="Write horizon_doctor.json.")

    conflicts = subparsers.add_parser("conflicts", help="Build horizon conflict matrix.")
    conflicts.add_argument("--write", action="store_true", help="Write horizon_conflicts.json.")

    next_cmd = subparsers.add_parser("next", help="Recommend next horizons.")
    next_cmd.add_argument("--limit", type=int, default=None, help="Maximum recommendations to emit.")
    next_cmd.add_argument("--write", action="store_true", help="Write horizon_next.json.")

    claim = subparsers.add_parser("claim", help="Claim a horizon lock.")
    claim.add_argument("horizon")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--ttl", type=int, default=7200, help="Lock TTL in seconds.")
    claim.add_argument("--dry-run", action="store_true", help="Validate without writing horizon_locks.json.")

    release = subparsers.add_parser("release", help="Release a horizon lock.")
    release.add_argument("horizon")
    release.add_argument("--agent", required=True)
    release.add_argument("--dry-run", action="store_true", help="Validate without writing horizon_locks.json.")

    events = subparsers.add_parser("events", help="Summarize horizon event log.")
    events.add_argument("--tail", type=int, default=10, help="Number of latest events to include.")

    subparsers.add_parser("preflight", help="Delegate to H46 preflight when available.")
    subparsers.add_parser("land", help="Delegate to H47 safe-land when available.")
    render = subparsers.add_parser("render", help="Render dashboard, DAG, and history artifacts.")
    render.add_argument("--target", choices=("dashboard", "dag", "history", "all"), action="append", default=None, help="Render target. Repeatable; defaults to all.")
    render.add_argument("--output", default=None, help="Output path for a single dashboard or DAG target.")
    render.add_argument("--theme", choices=("auto", "light", "dark"), default="auto", help="Dashboard theme.")
    render.add_argument("--snapshot-dir", default=None, help="Directory for history snapshots. Defaults below generated dir.")

    hook = subparsers.add_parser("hook", help="Run daemon-independent local horizon hook checks.")
    hook.add_argument("--mode", choices=("pre_commit", "pre_push", "manual"), default="manual")
    hook.add_argument("--changed-path", action="append", default=None, help="Changed path to check. Defaults to git diff.")
    hook.add_argument("--claim", action="append", default=None, help="Claimed horizon id. Repeatable.")
    hook.add_argument("--agent", default="local-hook", help="Agent id used for H46 preflight checks.")
    hook.add_argument("--no-inventory-only", action="store_true", help="Block inventory-only churn.")
    return parser


def run_command(args: argparse.Namespace, io: CommandIO | None = None, context: CommandContext | None = None) -> CommandResult:
    del io
    ctx = context or _context_from_args(args)
    handlers: dict[str, Callable[[argparse.Namespace, CommandContext], CommandResult]] = {
        "state": _run_state,
        "corpora": _run_corpora,
        "doctor": _run_doctor,
        "conflicts": _run_conflicts,
        "next": _run_next,
        "claim": _run_claim,
        "release": _run_release,
        "events": _run_events,
        "hook": _run_hook,
        "preflight": _run_delegated_stub,
        "land": _run_delegated_stub,
        "render": _run_render,
    }
    handler = handlers.get(args.command)
    if handler is None:
        return _with_context(CommandResult(False, str(args.command), message="unknown command", exit_code=ExitCode.BAD_INVOCATION), ctx)
    try:
        return _with_context(handler(args, ctx), ctx)
    except ValueError as exc:
        return _with_context(CommandResult(False, args.command, message=str(exc), exit_code=ExitCode.VALIDATION_FAILURE), ctx)
    except Exception as exc:  # pragma: no cover - defensive process boundary
        return _with_context(CommandResult(False, args.command, message=str(exc), exit_code=ExitCode.INTERNAL_ERROR), ctx)


def emit_result(result: CommandResult, output_format: str = "text", io: CommandIO | None = None) -> None:
    streams = io or CommandIO()
    if output_format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), file=streams.stdout)
        return
    stream = streams.stdout if result.ok else streams.stderr
    status = "ok" if result.ok else "error"
    print(f"{status}: {result.command}: {result.message or _default_message(result)}", file=stream)
    context = result.data.get("context")
    if isinstance(context, dict) and context.get("corpus"):
        print(f"context: corpus={context['corpus']} horizons_dir={context.get('horizons_dir', '')}", file=stream)
    for diagnostic in result.diagnostics:
        print(f"- {diagnostic}", file=stream)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .interactive import run_interactive_main

        return run_interactive_main()
    parser = build_parser()
    args = parser.parse_args(argv)
    io = CommandIO()
    result = run_command(args, io=io)
    emit_result(result, args.format, io)
    return int(result.exit_code)


def _run_state(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .parser import parse_horizon_tree

    state = parse_horizon_tree(ctx.horizons_dir)
    if args.write:
        state.write_json(ctx.path("horizon_state.json"))
    return CommandResult(
        True,
        "state",
        data={"horizon_count": len(state.records), "warning_count": len(state.warnings), "state": state.to_dict()},
        message=f"{len(state.records)} horizons parsed",
    )


def _run_corpora(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    action = getattr(args, "corpus_action", "list")
    rows = []
    corpora = known_corpora()
    path_diagnostics = validate_corpus_paths(corpora)
    diagnostics_by_corpus: dict[str, list[dict[str, str]]] = {}
    for diagnostic in path_diagnostics:
        diagnostics_by_corpus.setdefault(diagnostic.corpus, []).append(diagnostic.to_dict())
    for corpus in corpora:
        payload = _corpus_row(corpus, ctx)
        payload["diagnostics"] = diagnostics_by_corpus.get(corpus.name, [])
        payload["healthy"] = not payload["diagnostics"]
        rows.append(payload)
    ok = not path_diagnostics
    if action == "doctor":
        return CommandResult(
            ok,
            "corpora",
            data={
                "action": "doctor",
                "corpora": rows,
                "diagnostic_count": len(path_diagnostics),
                "diagnostics": [item.to_dict() for item in path_diagnostics],
                "selected": str(ctx.horizons_dir),
            },
            message="corpus registry healthy" if ok else "corpus registry diagnostics found",
            exit_code=ExitCode.SUCCESS if ok else ExitCode.VALIDATION_FAILURE,
            diagnostics=tuple(f"{item.corpus}:{item.field}:{item.code}" for item in path_diagnostics),
        )
    return CommandResult(
        True,
        "corpora",
        data={
            "action": "list",
            "corpora": rows,
            "diagnostic_count": len(path_diagnostics),
            "selected": str(ctx.horizons_dir),
        },
        message=f"{len(rows)} corpora",
    )


def _run_doctor(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .doctor import run_doctor
    from .parser import parse_horizon_tree

    state = parse_horizon_tree(ctx.horizons_dir)
    report = run_doctor(state, repo_root=ctx.repo_root, generated_paths=_generated_files(ctx))
    if args.write:
        ctx.path("horizon_doctor.json").write_text(report.to_json(), encoding="utf-8")
    exit_code = ExitCode.SUCCESS if report.ok else ExitCode.VALIDATION_FAILURE
    return CommandResult(
        report.ok,
        "doctor",
        data=report.to_dict(),
        message="diagnostics passed" if report.ok else "diagnostics found errors",
        exit_code=exit_code,
    )


def _run_conflicts(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .conflicts import build_conflict_matrix
    from .parser import parse_horizon_tree

    state = parse_horizon_tree(ctx.horizons_dir)
    matrix = build_conflict_matrix(state)
    if args.write:
        matrix.write_json(ctx.path("horizon_conflicts.json"))
    return CommandResult(
        True,
        "conflicts",
        data=matrix.to_dict(),
        message=f"{len(matrix.conflicts)} conflicts, {len(matrix.blocking_pairs)} blocking pairs",
    )


def _run_next(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .conflicts import build_conflict_matrix
    from .doctor import run_doctor
    from .locks import LockStore
    from .next import recommend_next
    from .parser import parse_horizon_tree

    state = parse_horizon_tree(ctx.horizons_dir)
    doctor = run_doctor(state, repo_root=ctx.repo_root, generated_paths=_generated_files(ctx))
    conflicts = build_conflict_matrix(state)
    locks = LockStore(ctx.path("horizon_locks.json")).load()
    report = recommend_next(state, doctor, conflicts, locks, now=ctx.now or None, limit=args.limit)
    if args.write:
        ctx.path("horizon_next.json").write_text(report.to_json(), encoding="utf-8")
    return CommandResult(
        True,
        "next",
        data=report.to_dict(),
        message=f"{len(report.recommendations)} recommendations",
    )


def _run_claim(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .conflicts import build_conflict_matrix
    from .locks import LockStore, claim_horizon
    from .parser import parse_horizon_tree

    state = parse_horizon_tree(ctx.horizons_dir)
    conflicts = build_conflict_matrix(state)
    store = LockStore(ctx.path("horizon_locks.json"))
    snapshot = store.load()
    next_snapshot, decision = claim_horizon(state, conflicts, snapshot, args.horizon, args.agent, args.ttl, now=ctx.now or None)
    if decision.ok and not args.dry_run:
        store.save(next_snapshot)
    exit_code = ExitCode.SUCCESS if decision.ok else _lock_failure_code(decision.blockers)
    return CommandResult(
        decision.ok,
        "claim",
        data={"decision": decision.to_dict(), "snapshot": next_snapshot.to_dict(), "dry_run": bool(args.dry_run)},
        message="claim accepted" if decision.ok else "claim rejected",
        exit_code=exit_code,
        diagnostics=decision.blockers or decision.warnings,
    )


def _run_release(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .locks import LockStore, release_horizon

    store = LockStore(ctx.path("horizon_locks.json"))
    snapshot = store.load()
    next_snapshot, decision = release_horizon(snapshot, args.horizon, args.agent, now=ctx.now or None)
    if decision.ok and not args.dry_run:
        store.save(next_snapshot)
    exit_code = ExitCode.SUCCESS if decision.ok else ExitCode.MISSING_CLAIM
    return CommandResult(
        decision.ok,
        "release",
        data={"decision": decision.to_dict(), "snapshot": next_snapshot.to_dict(), "dry_run": bool(args.dry_run)},
        message="release accepted" if decision.ok else "release rejected",
        exit_code=exit_code,
        diagnostics=decision.blockers or decision.warnings,
    )


def _run_events(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    path = ctx.path("horizon_events.jsonl")
    events = []
    if path.exists():
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tail = events[-max(args.tail, 0) :] if args.tail else []
    return CommandResult(
        True,
        "events",
        data={"event_count": len(events), "events": tail},
        message=f"{len(events)} events",
    )


def _run_hook(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .conflicts import build_conflict_matrix
    from .doctor import run_doctor
    from .hooks import HookContext, collect_git_changed_paths, render_hook_report, run_hook
    from .locks import LockStore
    from .parser import parse_horizon_tree

    changed = tuple(Path(path) for path in (args.changed_path or ())) or collect_git_changed_paths(args.mode, ctx.repo_root)
    state = parse_horizon_tree(ctx.horizons_dir)
    locks = LockStore(ctx.path("horizon_locks.json")).load()
    doctor = run_doctor(state, repo_root=ctx.repo_root, generated_paths=_generated_files(ctx))
    conflicts = build_conflict_matrix(state)
    report = run_hook(
        args.mode,
        HookContext(
            changed_paths=changed,
            repo_root=ctx.repo_root,
            generated_dir=ctx.generated_dir,
            claimed_horizons=tuple(args.claim or ()),
            agent_id=args.agent,
            state=state,
            locks=locks,
            doctor_report=doctor,
            conflict_matrix=conflicts,
            now=ctx.now or None,
            allow_inventory_only=not args.no_inventory_only,
        ),
    )
    exit_code = ExitCode.SUCCESS if report.ok else ExitCode.VALIDATION_FAILURE
    return CommandResult(
        report.ok,
        "hook",
        data={"report": report.to_dict(), "rendered": render_hook_report(report, "text")},
        message="hook checks passed" if report.ok else "hook checks blocked",
        exit_code=exit_code,
        diagnostics=report.diagnostics,
    )


def _run_render(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    from .conflicts import build_conflict_matrix
    from .dag_render import build_dag_model, render_dag_html, write_dag
    from .doctor import run_doctor
    from .history import build_snapshot, summarize_since_last, write_snapshot
    from .locks import LockStore
    from .next import recommend_next
    from .parser import parse_horizon_tree
    from .render import build_dashboard_model, render_dashboard, write_dashboard

    targets = _render_targets(args.target)
    output_override = Path(args.output) if args.output else None
    if output_override is not None and len(targets) != 1:
        raise ValueError("--output can only be used with one render target")

    state = parse_horizon_tree(ctx.horizons_dir)
    doctor = run_doctor(state, repo_root=ctx.repo_root, generated_paths=_generated_files(ctx))
    conflicts = build_conflict_matrix(state)
    locks = LockStore(ctx.path("horizon_locks.json")).load()
    next_report = recommend_next(state, doctor, conflicts, locks, now=ctx.now or None)
    events = _read_event_rows(ctx.path("horizon_events.jsonl"))
    artifacts: dict[str, str] = {}
    counts: dict[str, int] = {}
    dashboard_html = ""

    if "dashboard" in targets or "history" in targets:
        dashboard_model = build_dashboard_model(state, doctor, conflicts, locks, next_report, events)
        dashboard_html = render_dashboard(dashboard_model, theme=args.theme, title=f"{ctx.corpus_title} Mission Control")
        if "dashboard" in targets:
            dashboard_path = output_override if output_override is not None else ctx.path("horizon_dashboard.html")
            write_dashboard(dashboard_path, dashboard_html)
            artifacts["dashboard"] = str(dashboard_path)
            counts["dashboard_sections"] = len(dashboard_model.sections)

    if "dag" in targets:
        dag_model = build_dag_model(state, conflicts, locks)
        dag_html = render_dag_html(dag_model, title=f"{ctx.corpus_title} Dependency DAG")
        dag_path = output_override if output_override is not None else ctx.path("horizon_dependency_graph.html")
        write_dag(dag_path, dag_html)
        artifacts["dag"] = str(dag_path)
        counts["dag_nodes"] = len(dag_model.nodes)
        counts["dag_edges"] = len(dag_model.edges)

    if "history" in targets:
        snapshot_dir = Path(args.snapshot_dir) if args.snapshot_dir else ctx.path("horizon_snapshots")
        snapshot = build_snapshot(
            state=state,
            conflicts=conflicts,
            locks=locks,
            recommendations=next_report,
            events=events,
            dashboard=dashboard_html,
            created_at=ctx.now or None,
            metadata={"corpus": ctx.corpus_name, "corpus_title": ctx.corpus_title, "generated_dir": str(ctx.generated_dir)},
        )
        changes = summarize_since_last(snapshot_dir, snapshot)
        snapshot_path = write_snapshot(snapshot_dir, snapshot)
        artifacts["history"] = str(snapshot_path)
        counts["history_changes"] = int(changes.has_changes)

    return CommandResult(
        True,
        "render",
        data={"artifacts": artifacts, "counts": counts, "targets": list(targets)},
        message=f"rendered {', '.join(targets)}",
    )


def _run_delegated_stub(args: argparse.Namespace, ctx: CommandContext) -> CommandResult:
    del ctx
    command = str(args.command)
    module_by_command = {"preflight": "H46", "land": "H47", "render": "H48"}
    horizon = module_by_command[command]
    return CommandResult(
        False,
        command,
        data={"delegate": horizon},
        message=f"{command} is waiting for {horizon} implementation",
        exit_code=ExitCode.VALIDATION_FAILURE,
        diagnostics=(f"delegate_not_ready:{horizon}",),
    )


def _corpus_row(corpus: HorizonCorpus, ctx: CommandContext) -> dict[str, Any]:
    payload = corpus.to_dict()
    payload["exists"] = corpus.horizons_dir.exists()
    payload["generated_dir_exists"] = corpus.generated_dir.exists()
    payload["horizon_count"] = _horizon_count(corpus.horizons_dir)
    payload["repo_root_exists"] = corpus.repo_root.exists()
    payload["selected"] = corpus.name == ctx.corpus_name or corpus.horizons_dir == ctx.horizons_dir
    return payload


def _horizon_count(horizons_dir: Path) -> int:
    if not horizons_dir.is_dir():
        return 0
    return sum(1 for _ in horizons_dir.glob("H[0-9][0-9]*/README.md"))


def _with_context(result: CommandResult, ctx: CommandContext) -> CommandResult:
    data = dict(result.data)
    data.setdefault("context", ctx.to_dict())
    return CommandResult(
        result.ok,
        result.command,
        data=data,
        message=result.message,
        exit_code=result.exit_code,
        diagnostics=result.diagnostics,
    )


def _context_from_args(args: argparse.Namespace) -> CommandContext:
    repo_root = Path(args.repo_root) if args.repo_root else None
    horizons_dir = Path(args.horizons_dir) if args.horizons_dir else None
    generated_dir = Path(args.generated_dir) if args.generated_dir else None
    return CommandContext(
        repo_root=repo_root,
        corpus_name=getattr(args, "corpus", None),
        horizons_dir=horizons_dir,
        generated_dir=generated_dir,
    )


def _generated_files(ctx: CommandContext) -> tuple[str, ...]:
    assert ctx.generated_dir is not None
    return tuple(str(path.relative_to(ctx.repo_root)) if path.is_relative_to(ctx.repo_root) else str(path) for path in sorted(ctx.generated_dir.glob("horizon_*.json*")))


def _render_targets(values: list[str] | None) -> tuple[str, ...]:
    requested = tuple(values or ("all",))
    if "all" in requested:
        return ("dashboard", "dag", "history")
    return tuple(dict.fromkeys(requested))


def _read_event_rows(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return tuple(rows)


def _lock_failure_code(blockers: tuple[str, ...]) -> ExitCode:
    if any(item.startswith(("conflict:", "lock:")) for item in blockers):
        return ExitCode.CONFLICT
    if any(item.startswith(("not_active:", "owner:")) for item in blockers):
        return ExitCode.MISSING_CLAIM
    return ExitCode.VALIDATION_FAILURE


def _default_message(result: CommandResult) -> str:
    if "count" in result.data:
        return str(result.data["count"])
    return "completed"


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
