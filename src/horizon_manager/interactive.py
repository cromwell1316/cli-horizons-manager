"""Keyboard-first console surface for Horizon Manager."""

from __future__ import annotations

import sys
import termios
import tty
from collections.abc import Callable, Sequence

from .cli import CommandContext, build_parser, emit_result, run_command
from .corpus import known_corpora


CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_DIM = "\033[90m"


MenuRunner = Callable[..., int]


def clear_screen(stdout=None) -> None:
    stream = sys.stdout if stdout is None else stdout
    stream.write("\033[H\033[J")
    stream.flush()


def render_menu_lines(options: Sequence[str], title: str = "", selected_idx: int = 0, pre_lines: Sequence[str] | None = None) -> list[str]:
    lines = [
        f"{CLR_BOLD}{CLR_CYAN}{title or 'HORIZON MANAGER'}{CLR_RESET}",
        "",
    ]
    if pre_lines:
        lines.extend(str(line) for line in pre_lines)
        lines.append("")
    for idx, option in enumerate(options):
        if idx == selected_idx:
            lines.append(f"  {CLR_BOLD}{CLR_CYAN}--> \033[40m\033[1;37m{option}{CLR_RESET}")
        else:
            lines.append(f"      {CLR_DIM}{option}{CLR_RESET}")
    lines.append("")
    lines.append(
        f"{CLR_WHITE}Use {CLR_BOLD}up/down{CLR_RESET}{CLR_WHITE}, digits/shortcuts, "
        f"{CLR_BOLD}Enter{CLR_RESET}{CLR_WHITE} to confirm, "
        f"{CLR_BOLD}Esc/q{CLR_RESET}{CLR_WHITE} to go back.{CLR_RESET}"
    )
    return lines


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
            _run_direct(["state", "--write"], context)
            _run_direct(["doctor", "--write"], context)
            _run_direct(["conflicts", "--write"], context)
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
        pre_lines=(
            "Keyboard-first mission control for configured horizon corpora.",
            f"Active corpus: {context.corpus_name}",
            f"Horizons: {context.horizons_dir}",
        ),
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
    print(build_parser().format_help())


def _run_direct(argv: list[str], context: CommandContext) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_command(args, context=context)
    emit_result(result, getattr(args, "format", "text"))
    return int(result.exit_code)


def _prompt(label: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _pause() -> None:
    try:
        input("\nPress Enter to continue...")
    except EOFError:
        pass
