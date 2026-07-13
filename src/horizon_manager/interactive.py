"""Keyboard-first console surface for Horizon Manager."""

from __future__ import annotations

import sys
import termios
import textwrap
import tty
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .cli import CommandContext, build_parser, run_command
from .corpus import known_corpora


CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_BRIGHT_RED = "\033[38;5;196m"
CLR_DARK_RED = "\033[38;5;88m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_DIM = "\033[90m"
CLR_MUTED = "\033[38;5;245m"
CLR_BG_BLACK = "\033[48;5;0m"
_ANSI_RE = re.compile(r"\033\[[0-9;?]*[A-Za-z]")
STATUS_VALUE_COLUMN = 12
COMMAND_TITLES = {
    "next": "Overview / Next Horizons",
    "state": "Refresh State",
    "doctor": "Doctor",
    "conflicts": "Conflicts",
    "claim": "Claim Horizon",
    "release": "Release Horizon",
    "events": "Events",
    "hook": "Hook Preflight",
}


MenuRunner = Callable[..., int]


@dataclass(frozen=True)
class OperatorSnapshot:
    corpus_name: str
    corpus_title: str
    horizons_dir: str
    horizon_total: int | None = None
    status_counts: dict[str, int] | None = None
    active_locks: int | None = None
    total_locks: int | None = None
    doctor_ok: bool | None = None
    diagnostics: int | None = None
    worktree_dirty: int | None = None
    worktree_unknown: bool = False
    error: str = ""


def clear_screen(stdout=None) -> None:
    stream = sys.stdout if stdout is None else stdout
    stream.write(f"\033[?25h{CLR_BG_BLACK}\033[H\033[2J\033[3J")
    stream.flush()


def visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", str(text)))


def terminal_size(fallback: tuple[int, int] = (120, 30)) -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback)
    return size.columns, size.lines


def themed_line(text: str = "", width: int | None = None) -> str:
    width = max(1, width or terminal_size()[0])
    body = str(text).replace(CLR_RESET, CLR_RESET + CLR_BG_BLACK)
    padding = " " * max(0, width - visible_len(body))
    return f"{CLR_BG_BLACK}{body}{padding}{CLR_RESET}"


def themed_screen_lines(lines: Sequence[str], width: int | None = None, height: int | None = None, top_padding: int = 1, left_padding: int | None = None) -> list[str]:
    term_width, term_height = terminal_size()
    width = max(1, width or term_width)
    height = max(1, height or term_height)
    if left_padding is None:
        left_padding = 4 if width >= 100 else 2
    left = " " * max(0, min(left_padding, max(0, width - 1)))
    themed = [themed_line(width=width) for _ in range(max(0, top_padding))]
    for line in lines:
        content_width = max(1, width - visible_len(left))
        themed.extend(themed_line(left + wrapped, width) for wrapped in _wrap_content_line(str(line), content_width))
    while len(themed) < height:
        themed.append(themed_line(width=width))
    return themed[:height]


def themed_block_lines(
    lines: Sequence[str],
    width: int | None = None,
    min_height: int | None = None,
    top_padding: int = 1,
    left_padding: int | None = None,
) -> list[str]:
    term_width, term_height = terminal_size()
    width = max(1, width or term_width)
    min_height = max(0, min_height if min_height is not None else 0)
    if left_padding is None:
        left_padding = 4 if width >= 100 else 2
    left = " " * max(0, min(left_padding, max(0, width - 1)))
    themed = [themed_line(width=width) for _ in range(max(0, top_padding))]
    content_width = max(1, width - visible_len(left))
    for line in lines:
        themed.extend(themed_line(left + wrapped, width) for wrapped in _wrap_content_line(str(line), content_width))
    while len(themed) < min(min_height, term_height):
        themed.append(themed_line(width=width))
    return themed


def _wrap_content_line(line: str, width: int) -> list[str]:
    if visible_len(line) <= width:
        return [line]
    if _ANSI_RE.search(line):
        return [line]
    indent_match = re.match(r"\s*", line)
    indent = indent_match.group(0) if indent_match else ""
    subsequent_indent = indent if visible_len(indent) < width else ""
    return textwrap.wrap(
        line,
        width=max(1, width),
        subsequent_indent=subsequent_indent,
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def header_lines(title: str = "", width: int | None = None) -> list[str]:
    term_width = terminal_size()[0]
    label = title or "HORIZON MANAGER"
    width = width or min(max(42, visible_len(label) + 18), term_width)
    width = max(1, min(width, term_width))
    divider = "━" * width
    return [
        f"{CLR_BOLD}{CLR_BRIGHT_RED}HORIZON MANAGER{CLR_RESET}{CLR_WHITE} {label if label != 'HORIZON MANAGER' else ''}{CLR_RESET}".rstrip(),
        f"{CLR_DARK_RED}{divider}{CLR_RESET}",
    ]


def render_menu_lines(options: Sequence[str], title: str = "", selected_idx: int = 0, pre_lines: Sequence[str] | None = None) -> list[str]:
    width, height = terminal_size()
    header_width = min(width, max(56, visible_len(title or "HORIZON MANAGER") + 18))
    lines = [*header_lines(title or "HORIZON MANAGER", width=header_width), ""]
    if pre_lines:
        reserved_lines = len(lines) + 1 + len(options) + 2
        fitted_pre_lines = _fit_pre_lines(pre_lines, max_lines=max(0, height - reserved_lines))
        lines.extend(str(line) for line in fitted_pre_lines)
        lines.append("")
    lines.append(f"{CLR_DIM}Actions{CLR_RESET}")
    for idx, option in enumerate(options):
        if idx == selected_idx:
            lines.append(f"{CLR_BRIGHT_RED}▌{CLR_RESET} {CLR_BOLD}{CLR_WHITE}{option}{CLR_RESET}")
        else:
            lines.append(f"  {CLR_MUTED}{option}{CLR_RESET}")
    lines.append("")
    lines.append(
        f"{CLR_MUTED}↑/↓ move   digits/shortcuts   "
        f"{CLR_BRIGHT_RED}Enter{CLR_RESET}{CLR_BG_BLACK}{CLR_DIM} select   "
        f"{CLR_BRIGHT_RED}Esc/q{CLR_RESET}{CLR_BG_BLACK}{CLR_DIM} back{CLR_RESET}"
    )
    return themed_screen_lines(lines)


def _fit_pre_lines(pre_lines: Sequence[str], *, max_lines: int) -> tuple[str, ...]:
    """Keep the keyboard menu visible in short terminals."""

    normalized = tuple(str(line) for line in pre_lines)
    if len(normalized) <= max_lines:
        return normalized
    if max_lines <= 0:
        return ()
    if max_lines == 1:
        return (f"{CLR_MUTED}Status shortened; use Refresh/Doctor for details.{CLR_RESET}",)
    return (
        *normalized[: max_lines - 1],
        f"{CLR_MUTED}... status shortened to keep actions visible{CLR_RESET}",
    )


def run_menu(options: Sequence[str], title: str = "", shortcuts: dict[str, int] | None = None, pre_lines: Sequence[str] | None = None) -> int:
    shortcuts = shortcuts or {}
    selected_idx = 0
    while True:
        clear_screen()
        print("\n".join(render_menu_lines(options, title, selected_idx, pre_lines=pre_lines)))
        key = get_key()
        if key == "up":
            selected_idx = (selected_idx - 1) % len(options)
        elif key == "down":
            selected_idx = (selected_idx + 1) % len(options)
        elif key == "enter":
            return selected_idx
        elif key.isdigit() and key != "0":
            idx = int(key) - 1
            if 0 <= idx < len(options):
                return idx
        elif key in shortcuts:
            return shortcuts[key]
        elif key in {"esc", "q"}:
            return -1
        elif key == "ctrl+c":
            raise KeyboardInterrupt


def get_key() -> str:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char == "\x03":
            return "ctrl+c"
        if char in {"\r", "\n"}:
            return "enter"
        if char == "\x1b":
            next_chars = sys.stdin.read(2)
            if next_chars == "[A":
                return "up"
            if next_chars == "[B":
                return "down"
            return "esc"
        return char.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_interactive_main(ctx: CommandContext | None = None, menu_runner: MenuRunner | None = None) -> int:
    context = ctx or CommandContext()
    choose = menu_runner or _default_menu_runner
    while True:
        options = [
            "[0] Corpora",
            "[1] Overview / Next Horizons",
            "[2] Refresh State + Doctor + Conflicts",
            "[3] Claim Horizon",
            "[4] Release Horizon",
            "[5] Events",
            "[6] Hook Check",
            "[7] Help",
            "[x] Exit",
        ]
        selected = _choose(choose, options, context, title="HORIZON MANAGER")
        if selected in {-1, 8}:
            clear_screen()
            print("Exiting Horizon Manager.")
            return 0
        if selected == 0:
            next_context = _select_corpus(context, choose)
            if next_context is not None:
                context = next_context
        elif selected == 1:
            _run_direct(["next", "--limit", "8"], context)
        elif selected == 2:
            _show_command_screen(("refresh",), context, title="Refresh State + Doctor + Conflicts")
            _run_direct(["state", "--write"], context, clear=False)
            _run_direct(["doctor", "--write"], context, clear=False)
            _run_direct(["conflicts", "--write"], context, clear=False)
        elif selected == 3:
            horizon = _prompt("Horizon id")
            agent = _prompt("Agent id", default="manual")
            if horizon:
                _run_direct(["claim", horizon, "--agent", agent], context)
        elif selected == 4:
            horizon = _prompt("Horizon id")
            agent = _prompt("Agent id", default="manual")
            if horizon:
                _run_direct(["release", horizon, "--agent", agent], context)
        elif selected == 5:
            _run_direct(["events", "--tail", "20"], context)
        elif selected == 6:
            _run_direct(["hook", "--mode", "manual"], context)
        elif selected == 7:
            _show_help()
        _pause()


def _default_menu_runner(options: Sequence[str], context: CommandContext, title: str = "HORIZON MANAGER") -> int:
    return run_menu(
        options,
        title,
        shortcuts={"0": 0, "x": 8},
        pre_lines=operator_status_lines(context),
    )


def _choose(choose: MenuRunner, options: Sequence[str], context: CommandContext, *, title: str) -> int:
    try:
        return int(choose(options, context, title))
    except TypeError:
        return int(choose(options))


def _select_corpus(context: CommandContext, choose: MenuRunner) -> CommandContext | None:
    corpora = known_corpora()
    options = [f"[{idx + 1}] {corpus.name} - {corpus.title}" for idx, corpus in enumerate(corpora)]
    options.append("[x] Back")
    selected = _choose(choose, options, context, title="SELECT CORPUS")
    if selected in {-1, len(options) - 1}:
        return None
    if 0 <= selected < len(corpora):
        corpus = corpora[selected]
        print(f"Selected corpus: {corpus.name}")
        return CommandContext(corpus_name=corpus.name)
    return None


def _show_help() -> None:
    _show_command_screen(("help",), CommandContext(), title="Help")
    print("\n".join(themed_block_lines(build_parser().format_help().splitlines(), min_height=max(1, terminal_size()[1] - 7), top_padding=0)))


def _run_direct(argv: list[str], context: CommandContext, *, clear: bool = True) -> int:
    if clear:
        _show_command_screen(argv, context)
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_command(args, context=context)
    _show_command_result(result)
    return int(result.exit_code)


def _show_command_screen(argv: Sequence[str], context: CommandContext, *, title: str | None = None) -> None:
    clear_screen()
    command = title or _command_title(argv)
    lines = [
        *header_lines("COMMAND", width=min(terminal_size()[0], 56)),
        "",
        _status_line("Command", command),
        _status_line("Corpus", f"{CLR_BRIGHT_RED}{context.corpus_name}{CLR_RESET}{CLR_BG_BLACK}{CLR_MUTED} - {context.corpus_title}{CLR_RESET}"),
        "",
    ]
    print("\n".join(themed_block_lines(lines)))


def _command_title(argv: Sequence[str]) -> str:
    command = str(argv[0]) if argv else "Command"
    return COMMAND_TITLES.get(command, " ".join(str(part) for part in argv) or "Command")


def _show_command_result(result: Any) -> None:
    if str(getattr(result, "command", "")) == "hook":
        print("\n".join(themed_block_lines(_hook_result_lines(result), top_padding=0)))
        return

    status = f"{CLR_BRIGHT_RED}ok{CLR_RESET}" if getattr(result, "ok", False) else f"{CLR_RED}blocked{CLR_RESET}"
    lines = [
        f"{CLR_DIM}Result{CLR_RESET}",
        _status_line("Status", status),
        _status_line("Message", _result_message(result)),
    ]
    context = (getattr(result, "data", {}) or {}).get("context")
    if isinstance(context, dict) and context.get("corpus"):
        horizons = _compact_path(context.get("horizons_dir", ""), max_width=max(32, terminal_size()[0] - 30))
        lines.append(_status_line("Context", f"corpus={context['corpus']} | horizons={horizons}"))
    diagnostics = tuple(str(item) for item in getattr(result, "diagnostics", ()) or ())
    if diagnostics:
        lines.append(f"{CLR_DIM}Diagnostics{CLR_RESET}")
        lines.extend(f"{CLR_RED}- {item}{CLR_RESET}" for item in diagnostics)
    feedback = command_feedback_lines(result)
    if feedback:
        lines.append(f"{CLR_DIM}Summary{CLR_RESET}")
        lines.extend(f"{CLR_MUTED}{line}{CLR_RESET}" for line in feedback)
    print("\n".join(themed_block_lines(lines, top_padding=0)))


def _hook_result_lines(result: Any) -> list[str]:
    report = (getattr(result, "data", {}) or {}).get("report", {}) or {}
    status = f"{CLR_BRIGHT_RED}ok{CLR_RESET}" if getattr(result, "ok", False) else f"{CLR_RED}blocked{CLR_RESET}"
    lines = [
        f"{CLR_DIM}Result{CLR_RESET}",
        _status_line("Status", status),
        _status_line("Message", _result_message(result)),
    ]
    context = (getattr(result, "data", {}) or {}).get("context")
    if isinstance(context, dict) and context.get("corpus"):
        lines.extend(
            (
                f"{CLR_DIM}Context{CLR_RESET}",
                _status_line("Corpus", str(context["corpus"])),
                _status_line("Horizons", _compact_path(context.get("horizons_dir", ""), max_width=max(32, terminal_size()[0] - 24))),
            )
        )

    diagnostics = tuple(str(item) for item in getattr(result, "diagnostics", ()) or report.get("diagnostics", ()) or ())
    if diagnostics:
        lines.append(f"{CLR_DIM}Blocking Issues{CLR_RESET}")
        lines.extend(f"{CLR_RED}- {item}{CLR_RESET}" for item in diagnostics)
    else:
        lines.append(f"{CLR_DIM}Blocking Issues{CLR_RESET}")
        lines.append(f"{CLR_MUTED}none{CLR_RESET}")

    changes = tuple(change for change in report.get("changes", ()) if isinstance(change, dict))
    if changes:
        lines.append(f"{CLR_DIM}Changed Files{CLR_RESET}")
        lines.extend(_hook_change_lines(changes))

    lines.append(f"{CLR_DIM}Summary{CLR_RESET}")
    lines.append(f"{CLR_MUTED}{_hook_summary_line(report, getattr(result, 'ok', False))}{CLR_RESET}")
    lines.append(f"{CLR_DIM}Next{CLR_RESET}")
    lines.extend(_hook_next_action_lines(report, diagnostics))
    return lines


def _hook_change_lines(changes: Sequence[dict[str, Any]], *, limit: int = 8) -> list[str]:
    lines: list[str] = []
    for change in changes[:limit]:
        classification = str(change.get("classification") or "unknown")
        horizon = str(change.get("horizon_id") or "").strip()
        path = str(change.get("path") or "")
        owner = f" {horizon}" if horizon else ""
        lines.append(f"{CLR_MUTED}- {classification}{owner}: {_compact_path(path, max_width=max(32, terminal_size()[0] - 30))}{CLR_RESET}")
    remaining = len(changes) - limit
    if remaining > 0:
        lines.append(f"{CLR_MUTED}- ... {remaining} more changed file(s){CLR_RESET}")
    return lines


def _hook_summary_line(report: dict[str, Any], ok: bool) -> str:
    changes = tuple(change for change in report.get("changes", ()) if isinstance(change, dict))
    diagnostics = tuple(report.get("diagnostics", ()) or ())
    classifications = _count_values(change.get("classification", "unknown") for change in changes)
    pieces = [
        f"Status: {'ok' if ok else 'blocked'}",
        f"Changed: {len(changes)}",
        f"Blocking: {len(diagnostics)}",
    ]
    pieces.extend(f"{_title_label(key)}: {value}" for key, value in classifications.items())
    return " | ".join(pieces)


def _hook_next_action_lines(report: dict[str, Any], diagnostics: Sequence[str]) -> list[str]:
    changes = tuple(change for change in report.get("changes", ()) if isinstance(change, dict))
    horizon_ids = tuple(str(item) for item in report.get("horizon_ids", ()) or ())
    lines: list[str] = []
    if horizon_ids and any("unclaimed horizon edits" in item for item in diagnostics):
        lines.append(f"{CLR_MUTED}- Claim affected horizon(s): {', '.join(horizon_ids)}.{CLR_RESET}")
    if any("detector output" in item for item in diagnostics):
        lines.append(f"{CLR_MUTED}- Move, accept, or revert detector output outside the hook mutation scope.{CLR_RESET}")
    if any(str(change.get("classification")) == "unrelated" for change in changes):
        lines.append(f"{CLR_MUTED}- Review unrelated paths manually before pre-push or commit hooks.{CLR_RESET}")
    guidance = str(report.get("bypass_guidance") or "").strip()
    if guidance:
        lines.append(f"{CLR_MUTED}- {guidance}{CLR_RESET}")
    if not lines:
        lines.append(f"{CLR_MUTED}- Rerun Hook Preflight before landing or handing off changes.{CLR_RESET}")
    return lines


def _result_message(result: Any) -> str:
    message = str(getattr(result, "message", "") or "")
    command = str(getattr(result, "command", "") or "command")
    return f"{command}: {message}" if message else command


def operator_status_lines(context: CommandContext) -> tuple[str, ...]:
    """Return deterministic, action-oriented status lines for the menu header."""

    snapshot = _operator_snapshot(context)
    decision, decision_color = _operator_decision(snapshot)
    return (
        f"{CLR_BOLD}{CLR_WHITE}{snapshot.corpus_name.upper()} Mission Control{CLR_RESET}",
        _status_line("Status", f"{decision_color}{decision}{CLR_RESET}"),
        _status_line("Corpus", f"{CLR_BRIGHT_RED}{snapshot.corpus_name}{CLR_RESET}{CLR_BG_BLACK}{CLR_MUTED} - {snapshot.corpus_title}{CLR_RESET}"),
        _status_line("State", _state_text(snapshot)),
        _status_line("Worktree", _worktree_text(snapshot)),
        _status_line("Next", _compact_next_action_text(snapshot)),
    )


def _operator_snapshot(context: CommandContext) -> OperatorSnapshot:
    snapshot = OperatorSnapshot(
        corpus_name=context.corpus_name,
        corpus_title=context.corpus_title,
        horizons_dir=str(context.horizons_dir),
    )
    try:
        from .doctor import run_doctor
        from .locks import LockStore
        from .parser import parse_horizon_tree

        state = parse_horizon_tree(context.horizons_dir)
        counts = _status_counts(state.records)
        locks = LockStore(context.path("horizon_locks.json")).load()
        doctor = run_doctor(state, repo_root=context.repo_root, generated_paths=())
        dirty_count, dirty_unknown = _dirty_path_count(context)
        return OperatorSnapshot(
            corpus_name=context.corpus_name,
            corpus_title=context.corpus_title,
            horizons_dir=str(context.horizons_dir),
            horizon_total=len(state.records),
            status_counts=counts,
            active_locks=len(locks.active_locks),
            total_locks=len(locks.locks),
            doctor_ok=doctor.ok,
            diagnostics=len(doctor.diagnostics),
            worktree_dirty=dirty_count,
            worktree_unknown=dirty_unknown,
        )
    except Exception as exc:  # pragma: no cover - defensive operator surface
        dirty_count, dirty_unknown = _dirty_path_count(context)
        return OperatorSnapshot(
            corpus_name=context.corpus_name,
            corpus_title=context.corpus_title,
            horizons_dir=str(context.horizons_dir),
            worktree_dirty=dirty_count,
            worktree_unknown=dirty_unknown,
            error=str(exc),
        )


def _operator_decision(snapshot: OperatorSnapshot) -> tuple[str, str]:
    if snapshot.error:
        return ("STATE UNAVAILABLE", CLR_RED)
    if snapshot.doctor_ok is False:
        return ("ACTIONS BLOCKED BY DOCTOR", CLR_RED)
    if snapshot.active_locks:
        return ("ACTIONS LIMITED BY ACTIVE LOCKS", CLR_RED)
    if (snapshot.worktree_dirty or 0) > 0:
        return ("READY, BUT WORKTREE NEEDS REVIEW", CLR_RED)
    if snapshot.worktree_unknown:
        return ("READY, BUT WORKTREE STATE IS UNKNOWN", CLR_MUTED)
    return ("READY TO CLAIM", CLR_BRIGHT_RED)


def _progress_text(snapshot: OperatorSnapshot) -> str:
    counts = snapshot.status_counts or {}
    if snapshot.horizon_total is None:
        return "unavailable"
    implemented = counts.get("implemented", 0)
    planned = counts.get("planned", 0)
    unknown = counts.get("unknown", 0)
    pieces = [f"{implemented} / {snapshot.horizon_total} implemented", f"{planned} planned"]
    if unknown:
        pieces.append(f"{unknown} unknown")
    for key, value in counts.items():
        if key not in {"implemented", "planned", "unknown"}:
            pieces.append(f"{value} {key}")
    return " | ".join(pieces)


def _state_text(snapshot: OperatorSnapshot) -> str:
    return f"{_progress_text(snapshot)} | {_health_text(snapshot, compact=True)}"


def _health_text(snapshot: OperatorSnapshot, *, compact: bool = False) -> str:
    if snapshot.error:
        return f"{CLR_RED}state unavailable{CLR_RESET}{CLR_BG_BLACK} | {snapshot.error}"
    doctor = f"{CLR_BRIGHT_RED}doctor ok{CLR_RESET}" if snapshot.doctor_ok else f"{CLR_RED}doctor blocked{CLR_RESET}"
    diagnostics = snapshot.diagnostics if snapshot.diagnostics is not None else "?"
    active_locks = snapshot.active_locks if snapshot.active_locks is not None else "?"
    total_locks = snapshot.total_locks if snapshot.total_locks is not None else "?"
    if compact:
        return f"{doctor}{CLR_BG_BLACK} | diag={diagnostics} | locks={active_locks}/{total_locks}"
    return f"{doctor}{CLR_BG_BLACK} | diagnostics={diagnostics} | locks={active_locks}/{total_locks}"


def _worktree_text(snapshot: OperatorSnapshot) -> str:
    if snapshot.error:
        return f"{CLR_RED}state unavailable; run refresh/doctor{CLR_RESET}"
    if snapshot.doctor_ok is False:
        return f"{CLR_RED}doctor diagnostics={snapshot.diagnostics or 0}; claim/release/hook blocked{CLR_RESET}"
    if snapshot.active_locks:
        return f"{CLR_RED}{snapshot.active_locks} active lock(s); ownership changes limited{CLR_RESET}"
    if snapshot.worktree_unknown:
        return f"{CLR_MUTED}unknown; run git status before horizon changes{CLR_RESET}"
    if (snapshot.worktree_dirty or 0) > 0:
        return f"{CLR_RED}{snapshot.worktree_dirty} dirty path(s); claim/release/hook blocked{CLR_RESET}"
    return f"{CLR_MUTED}clean; claim/release/hook available{CLR_RESET}"


def _compact_next_action_text(snapshot: OperatorSnapshot) -> str:
    if snapshot.error:
        return f"{CLR_RED}Refresh state, then inspect doctor output.{CLR_RESET}"
    if snapshot.doctor_ok is False:
        return f"{CLR_RED}Open Doctor details and fix diagnostics.{CLR_RESET}"
    if (snapshot.worktree_dirty or 0) > 0:
        return f"{CLR_RED}Review worktree changes; Refresh/Doctor stays available.{CLR_RESET}"
    if snapshot.worktree_unknown:
        return f"{CLR_MUTED}Run git status, then refresh state.{CLR_RESET}"
    return f"{CLR_MUTED}Run Hook Check, then claim or continue the next planned horizon.{CLR_RESET}"


def command_feedback_lines(result: Any) -> tuple[str, ...]:
    command = str(getattr(result, "command", ""))
    data = getattr(result, "data", {}) or {}
    if command == "doctor":
        diagnostics = data.get("diagnostics", ())
        severity_counts = data.get("severity_counts", {})
        return (
            "summary: doctor "
            f"{'ok' if getattr(result, 'ok', False) else 'blocked'}; "
            f"diagnostics={len(diagnostics)} errors={severity_counts.get('error', 0)} "
            f"warnings={severity_counts.get('warn', 0)}",
        )
    if command == "hook":
        report = data.get("report", {})
        return (_hook_summary_line(report, getattr(result, "ok", False)),)
    if command == "preflight":
        report = data.get("report", {})
        checks = report.get("checks", ())
        blockers = report.get("blockers", ())
        statuses = _count_values(check.get("status", "unknown") for check in checks if isinstance(check, dict))
        return (
            "summary: preflight "
            f"{'ok' if getattr(result, 'ok', False) else 'blocked'}; "
            f"checks={len(checks)} blockers={len(blockers)} statuses={_summary_counts(statuses)}",
        )
    return ()


def _prompt(label: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _pause() -> None:
    try:
        input(f"{CLR_BG_BLACK}    {CLR_MUTED}Press {CLR_WHITE}Enter{CLR_MUTED} to continue...{CLR_RESET}{CLR_BG_BLACK}\033[K")
    except EOFError:
        pass


def _status_counts(records: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = getattr(getattr(record, "status", "unknown"), "value", getattr(record, "status", "unknown"))
        text = str(value or "unknown")
        counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _operator_status_summary(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    preferred = ("implemented", "planned", "unknown", "blocked")
    parts = [f"{key}={counts[key]}" for key in preferred if key in counts]
    parts.extend(f"{key}={value}" for key, value in counts.items() if key not in preferred)
    return " | ".join(parts)


def _status_line(label: str, value: str, *, label_color: str = CLR_WHITE) -> str:
    label_text = f"{label}:"
    padding = " " * max(1, STATUS_VALUE_COLUMN - visible_len(label_text))
    return f"{label_color}{label_text}{CLR_RESET}{CLR_BG_BLACK}{padding}{value}"


def _compact_path(path: Any, *, max_width: int | None = None) -> str:
    text = str(path)
    width = max_width or max(48, min(86, terminal_size()[0] - 22))
    if visible_len(text) <= width:
        return text
    parts = [part for part in text.split("/") if part]
    if len(parts) < 4:
        return "..." + text[-max(1, width - 3) :]
    tail = "/".join(parts[-4:])
    prefix = "~" if text.startswith(str(Path.home())) else ""
    compact = f"{prefix}/.../{tail}" if prefix else f".../{tail}"
    if visible_len(compact) <= width:
        return compact
    return "..." + compact[-max(1, width - 3) :]


def _dirty_status(context: CommandContext) -> str:
    count, unknown = _dirty_path_count(context)
    if unknown:
        return "unknown"
    if not count:
        return f"{CLR_BRIGHT_RED}clean{CLR_RESET}"
    return f"{CLR_RED}dirty{CLR_RESET}{CLR_BG_BLACK} paths={count}"


def _dirty_path_count(context: CommandContext) -> tuple[int, bool]:
    root = context.repo_root
    if root is None:
        return 0, True
    result = subprocess.run(("git", "status", "--short", "--untracked-files=all"), cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return 0, True
    rows = tuple(line for line in result.stdout.splitlines() if line.strip())
    return len(rows), False


def _next_action_hint(worktree_status: str) -> str:
    plain = _ANSI_RE.sub("", worktree_status)
    if "dirty" in plain:
        return f"{CLR_RED}Review worktree before claim/release/hook actions.{CLR_RESET}"
    if "unknown" in plain:
        return f"{CLR_MUTED}Run Refresh State + Doctor before changing horizons.{CLR_RESET}"
    return f"{CLR_MUTED}Run Hook Check before landing or handing off changes.{CLR_RESET}"


def _count_values(values: Sequence[str] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value or "unknown")
        counts[text] = counts.get(text, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _summary_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ",".join(f"{key}={value}" for key, value in counts.items())


def _title_label(value: str) -> str:
    return str(value).replace("-", " ").title()
