"""Keyboard-first console surface for Horizon Manager."""

from __future__ import annotations

import sys
import termios
import tty
from collections.abc import Callable, Sequence
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
COMMAND_TITLES = {
    "next": "Overview / Next Horizons",
    "state": "Refresh State",
    "doctor": "Doctor",
    "conflicts": "Conflicts",
    "claim": "Claim Horizon",
    "release": "Release Horizon",
    "events": "Events",
    "hook": "Hook Check",
}


MenuRunner = Callable[..., int]


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
        themed.append(themed_line(left + str(line), width))
    while len(themed) < height:
        themed.append(themed_line(width=width))
    return themed[:height]


def themed_block_lines(lines: Sequence[str], width: int | None = None, top_padding: int = 1, left_padding: int | None = None) -> list[str]:
    term_width = terminal_size()[0]
    width = max(1, width or term_width)
    if left_padding is None:
        left_padding = 4 if width >= 100 else 2
    left = " " * max(0, min(left_padding, max(0, width - 1)))
    themed = [themed_line(width=width) for _ in range(max(0, top_padding))]
    themed.extend(themed_line(left + str(line), width) for line in lines)
    return themed


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
    width = terminal_size()[0]
    header_width = min(width, max(56, visible_len(title or "HORIZON MANAGER") + 18))
    lines = [*header_lines(title or "HORIZON MANAGER", width=header_width), ""]
    if pre_lines:
        lines.extend(str(line) for line in pre_lines)
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
    print(build_parser().format_help())


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


def _result_message(result: Any) -> str:
    message = str(getattr(result, "message", "") or "")
    command = str(getattr(result, "command", "") or "command")
    return f"{command}: {message}" if message else command


def operator_status_lines(context: CommandContext) -> tuple[str, ...]:
    """Return deterministic status lines for the themed menu header."""

    lines = [
        f"{CLR_WHITE}Keyboard-first mission control for configured horizon corpora.{CLR_RESET}",
        f"{CLR_DIM}Status{CLR_RESET}",
        _status_line("Corpus", f"{CLR_BRIGHT_RED}{context.corpus_name}{CLR_RESET}{CLR_BG_BLACK}{CLR_MUTED} - {context.corpus_title}{CLR_RESET}"),
        _status_line("Horizons", _compact_path(context.horizons_dir)),
    ]
    try:
        from .doctor import run_doctor
        from .locks import LockStore
        from .parser import parse_horizon_tree

        state = parse_horizon_tree(context.horizons_dir)
        counts = _status_counts(state.records)
        status_text = _operator_status_summary(counts)
        locks = LockStore(context.path("horizon_locks.json")).load()
        doctor = run_doctor(state, repo_root=context.repo_root, generated_paths=())
        doctor_state = f"{CLR_BRIGHT_RED}ok{CLR_RESET}" if doctor.ok else f"{CLR_RED}blocked{CLR_RESET}"
        lines.extend(
            (
                _status_line("Horizons", f"total={len(state.records)} | {status_text}"),
                _status_line("Locks", f"active={len(locks.active_locks)} | total={len(locks.locks)}"),
                _status_line("Doctor", f"{doctor_state}{CLR_BG_BLACK} | diagnostics={len(doctor.diagnostics)}{CLR_RESET}"),
            )
        )
    except Exception as exc:  # pragma: no cover - defensive operator surface
        lines.append(f"{CLR_RED}Corpus state unavailable:{CLR_RESET}{CLR_BG_BLACK} {exc}")
    worktree = _dirty_status(context)
    lines.append(_status_line("Worktree", worktree))
    lines.append(_status_line("Next", _next_action_hint(worktree), label_color=CLR_DIM))
    return tuple(lines)


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
        changes = report.get("changes", ())
        diagnostics = report.get("diagnostics", ())
        classifications = _count_values(change.get("classification", "unknown") for change in changes if isinstance(change, dict))
        return (
            "summary: hook "
            f"{'ok' if getattr(result, 'ok', False) else 'blocked'}; "
            f"changed={len(changes)} diagnostics={len(diagnostics)} classifications={_summary_counts(classifications)}",
        )
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
        input(f"\n{CLR_BG_BLACK}    {CLR_MUTED}Press {CLR_WHITE}Enter{CLR_MUTED} to continue...{CLR_RESET}{CLR_BG_BLACK}")
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
    return f"{label_color}{label}:{CLR_RESET}{CLR_BG_BLACK} {value}"


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
    root = context.repo_root
    if root is None:
        return "unknown"
    result = subprocess.run(("git", "status", "--short", "--untracked-files=all"), cwd=root, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return "unknown"
    rows = tuple(line for line in result.stdout.splitlines() if line.strip())
    if not rows:
        return f"{CLR_BRIGHT_RED}clean{CLR_RESET}"
    return f"{CLR_RED}dirty{CLR_RESET}{CLR_BG_BLACK} paths={len(rows)}"


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
