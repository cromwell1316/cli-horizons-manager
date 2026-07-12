"""Horizon README parser."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

from .model import (
    HorizonDependency,
    HorizonId,
    HorizonRecord,
    HorizonState,
    HorizonStatus,
    OwnedPath,
    OwnedPathMode,
    ParseWarning,
)


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_HORIZONS_DIR = REPO_ROOT / "management/subprojects/hermes-consistency-orchestrator/horizons"
DEFAULT_OUTPUT = REPO_ROOT / "management/subprojects/hermes-consistency-orchestrator/horizon_state.json"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_STATUS_RE = re.compile(r"^Status:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_WAVE_RE = re.compile(r"\bWave\s+(\d+)\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_HID_RE = re.compile(r"\b(?:HCO-)?H(\d{1,3})(?:\s*[-–]\s*(?:H)?(\d{1,3}))?\b", re.IGNORECASE)
_PATH_RE = re.compile(
    r"(?:(?:management|hco|tools|scripts|docs|src|tests|deep_audit)/[A-Za-z0-9_./*{}?@+=:,~%#-]+|"
    r"[A-Za-z0-9_./-]+\.(?:py|md|json|jsonl|html|sqlite|sh|toml|txt))"
)


def discover_readmes(horizons_dir: str | Path = DEFAULT_HORIZONS_DIR) -> list[Path]:
    root = Path(horizons_dir)
    return sorted(root.glob("H[0-9][0-9]*/README.md"), key=lambda path: HorizonId(path.parent.name).number)


def parse_horizon_tree(horizons_dir: str | Path = DEFAULT_HORIZONS_DIR) -> HorizonState:
    root = Path(horizons_dir)
    records = [parse_readme(path, root) for path in discover_readmes(root)]
    warnings: list[ParseWarning] = []
    if not records:
        warnings.append(ParseWarning("no_readmes", None, f"no horizon READMEs found under {root}", str(root), "discovery"))
    return HorizonState(records=tuple(records), warnings=tuple(warnings), generated_from=_rel(root))


def write_horizon_state(
    horizons_dir: str | Path = DEFAULT_HORIZONS_DIR,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> HorizonState:
    state = parse_horizon_tree(horizons_dir)
    state.write_json(output_path)
    return state


def parse_readme(path: str | Path, horizons_dir: str | Path | None = None) -> HorizonRecord:
    source_path = Path(path)
    root = Path(horizons_dir) if horizons_dir is not None else source_path.parents[1]
    text = source_path.read_text(encoding="utf-8")
    horizon_id = HorizonId(source_path.parent.name)
    warnings: list[ParseWarning] = []

    title = _parse_title(text, horizon_id)
    status_text = _match_text(_STATUS_RE.search(text))
    status = HorizonStatus.normalize(status_text)
    if not status_text:
        warnings.append(_warning("missing_status", horizon_id, source_path, "metadata", "missing Status line"))
    elif status is HorizonStatus.UNKNOWN:
        warnings.append(_warning("unknown_status", horizon_id, source_path, "metadata", f"unknown status: {status_text}"))

    sections = _scan_sections(text)
    concurrency = sections.get("concurrency", "").strip()
    if not concurrency:
        warnings.append(_warning("missing_concurrency", horizon_id, source_path, "Concurrency", "missing Concurrency section"))

    wave = _parse_wave(status_text, concurrency, text)
    if wave is None:
        warnings.append(_warning("missing_wave", horizon_id, source_path, "metadata", "missing Wave marker"))

    dependencies = _parse_dependencies(horizon_id, status_text, sections, text)
    owned_files = _parse_owned_files(horizon_id, source_path, sections)
    if not any(owned.mode is not OwnedPathMode.READ_ONLY for owned in owned_files):
        warnings.append(_warning("missing_owned_files", horizon_id, source_path, "Owned Files", "missing writable Owned Files section"))

    return HorizonRecord(
        id=horizon_id,
        title=title,
        directory=_rel(source_path.parent),
        source_path=_rel(source_path),
        status=status,
        wave=wave,
        dates=tuple(sorted(set(_DATE_RE.findall(status_text or "")))),
        dependencies=tuple(dependencies),
        owned_files=tuple(owned_files),
        concurrency=concurrency,
        warnings=tuple(warnings),
        metadata={
            "status_raw": status_text,
            "section_titles": sorted(sections),
        },
    )


def _scan_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    current_level: int | None = None
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = _normalize_heading(match.group(2))
            if level <= 2:
                current = title
                current_level = level
                sections.setdefault(current, [])
                continue
            if current is None or current_level is None or level <= current_level:
                current = title
                current_level = level
                sections.setdefault(current, [])
                continue
        if current:
            sections[current].append(line)
    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def _parse_title(text: str, horizon_id: HorizonId) -> str:
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        title = re.sub(rf"^(?:HCO-)?{re.escape(str(horizon_id))}\s*", "", title, flags=re.IGNORECASE)
        return title.strip(" -:") or str(horizon_id)
    return str(horizon_id)


def _parse_wave(*texts: str) -> int | None:
    for text in texts:
        if not text:
            continue
        match = _WAVE_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def _parse_dependencies(
    horizon_id: HorizonId,
    status_text: str,
    sections: dict[str, str],
    full_text: str,
) -> list[HorizonDependency]:
    candidates: list[tuple[str, str]] = []
    if status_text and _dependency_signal(status_text):
        candidates.append(("Status", status_text))
    for section_name, body in sections.items():
        if section_name in {"concurrency", "workstreams", "definition of done"} or _dependency_signal(body):
            candidates.append((section_name, body))
    dependencies: dict[tuple[str, str], HorizonDependency] = {}
    for source, body in candidates:
        for raw in _dependency_lines(body):
            for dep_id in _extract_ids(raw):
                if dep_id == horizon_id:
                    continue
                key = (str(dep_id), source)
                dependencies.setdefault(key, HorizonDependency(dep_id, _source_label(source, raw), raw.strip()))
    if not dependencies and _dependency_signal(full_text):
        for raw in _dependency_lines(full_text):
            for dep_id in _extract_ids(raw):
                if dep_id != horizon_id:
                    dependencies.setdefault((str(dep_id), "inferred"), HorizonDependency(dep_id, "inferred", raw.strip()))
    return sorted(dependencies.values(), key=lambda item: (item.id.number, item.source, item.raw))


def _dependency_signal(text: str) -> bool:
    lowered = text.lower()
    return "after h" in lowered or "needs:" in lowered or "←" in text or "depends on h" in lowered


def _dependency_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        for part in re.split(r"(?<=[.])\s+|;", line):
            if _dependency_signal(part):
                yield part


def _extract_ids(text: str) -> list[HorizonId]:
    ids: list[HorizonId] = []
    for match in _HID_RE.finditer(text):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        if end < start or end - start > 80:
            end = start
        for number in range(start, end + 1):
            ids.append(HorizonId(number))
    return ids


def _source_label(section: str, raw: str) -> str:
    lowered = raw.lower()
    if "needs:" in lowered:
        return "needs"
    if "after h" in lowered:
        return "after"
    if "←" in raw:
        return "arrow"
    if section == "concurrency":
        return "Concurrency"
    return section


def _parse_owned_files(
    horizon_id: HorizonId,
    source_path: Path,
    sections: dict[str, str],
) -> list[OwnedPath]:
    del horizon_id, source_path
    owned: dict[tuple[str, str, str], OwnedPath] = {}
    for section_name, body in sections.items():
        if "owned files" not in section_name and "consumed contracts" not in section_name:
            continue
        section_mode = _mode_from_section(section_name)
        for raw in _declaration_lines(body):
            paths = _extract_paths(raw)
            if not paths:
                continue
            mode = _mode_from_line(raw, section_mode)
            for path in paths:
                key = (path, mode.value, section_name)
                owned.setdefault(key, OwnedPath(path=path, mode=mode, raw=raw.strip(), section=section_name))
    return sorted(owned.values(), key=lambda item: (item.path, item.mode.value, item.section, item.raw))


def _declaration_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")) or "`" in stripped or "planned generated output " in stripped:
            yield stripped.lstrip("-* ").strip()


def _mode_from_section(section_name: str) -> OwnedPathMode:
    lowered = section_name.lower()
    if "consumed contracts" in lowered or "read" in lowered:
        return OwnedPathMode.READ_ONLY
    if "generated" in lowered:
        return OwnedPathMode.GENERATED
    if "shared" in lowered:
        return OwnedPathMode.SHARED
    if "exclusive" in lowered or "owned files" in lowered:
        return OwnedPathMode.EXCLUSIVE
    return OwnedPathMode.UNKNOWN


def _mode_from_line(raw: str, default: OwnedPathMode) -> OwnedPathMode:
    lowered = raw.lower()
    if "generated" in lowered or "planned generated output" in lowered:
        return OwnedPathMode.GENERATED
    if "read-only" in lowered or "read only" in lowered:
        return OwnedPathMode.READ_ONLY
    if "shared" in lowered or "coordinate" in lowered:
        return OwnedPathMode.SHARED
    if "exclusive" in lowered:
        return OwnedPathMode.EXCLUSIVE
    return default


def _extract_paths(raw: str) -> list[str]:
    paths: list[str] = []
    for chunk in re.findall(r"`([^`]+)`", raw):
        paths.extend(_split_path_chunk(chunk))
    remainder = re.sub(r"`[^`]+`", " ", raw)
    for match in _PATH_RE.finditer(remainder):
        paths.append(match.group(0).rstrip(".,;)"))
    return sorted(set(path for path in paths if _looks_like_path(path)))


def _split_path_chunk(chunk: str) -> list[str]:
    parts = re.split(r"\s*(?:;|,|\band\b|\bor\b)\s*", chunk)
    return [part.strip().rstrip(".,;)") for part in parts if _looks_like_path(part.strip())]


def _looks_like_path(value: str) -> bool:
    if not value or " " in value:
        return False
    return "/" in value or "." in value or value.endswith("*")


def _normalize_heading(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*", " ", value)
    value = value.replace("&", "and")
    value = re.sub(r"[^A-Za-z0-9]+", " ", value).strip().lower()
    return re.sub(r"\s+", " ", value)


def _match_text(match: re.Match[str] | None) -> str:
    return match.group(1).strip() if match else ""


def _warning(code: str, horizon_id: HorizonId, source_path: Path, section: str, message: str) -> ParseWarning:
    return ParseWarning(code=code, horizon_id=horizon_id, message=message, source_path=_rel(source_path), section=section)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate canonical HCO horizon state JSON.")
    parser.add_argument("--horizons-dir", default=str(DEFAULT_HORIZONS_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    state = write_horizon_state(args.horizons_dir, args.output)
    print(
        f"wrote {args.output}: horizons={len(state.records)} "
        f"edges={len(state.dependency_edges())} warnings={len(state.warnings)} "
        f"owned_paths={len(state.owned_path_index())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
