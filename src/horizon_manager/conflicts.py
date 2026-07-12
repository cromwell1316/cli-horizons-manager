"""Horizon conflict matrix."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
from typing import Iterable

from .model import HorizonId, HorizonRecord, HorizonState, OwnedPath, OwnedPathMode


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "management/horizon_conflicts.json"


class ConflictKind(Enum):
    WRITE_WRITE = "write_write"
    READ_WRITE = "read_write"
    GENERATED_ARTIFACT = "generated_artifact"
    FORBIDDEN_FILE = "forbidden_file"
    DEPENDENCY_ORDER = "dependency_order"
    NONE = "none"


class ConflictSeverity(Enum):
    BLOCK = "block"
    WARN = "warn"
    INFO = "info"


@dataclass(frozen=True, order=True)
class ConflictPath:
    path: str
    left_mode: OwnedPathMode
    right_mode: OwnedPathMode

    def __post_init__(self) -> None:
        if isinstance(self.left_mode, str):
            object.__setattr__(self, "left_mode", OwnedPathMode.normalize(self.left_mode))
        if isinstance(self.right_mode, str):
            object.__setattr__(self, "right_mode", OwnedPathMode.normalize(self.right_mode))

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "left_mode": self.left_mode.value,
            "right_mode": self.right_mode.value,
        }


@dataclass(frozen=True)
class Conflict:
    left: HorizonId
    right: HorizonId
    kind: ConflictKind
    severity: ConflictSeverity
    paths: tuple[ConflictPath, ...] = ()
    explanation: str = ""

    def __post_init__(self) -> None:
        left = HorizonId(self.left)
        right = HorizonId(self.right)
        if right.number < left.number:
            left, right = right, left
        object.__setattr__(self, "left", left)
        object.__setattr__(self, "right", right)
        if isinstance(self.kind, str):
            object.__setattr__(self, "kind", ConflictKind(self.kind))
        if isinstance(self.severity, str):
            object.__setattr__(self, "severity", ConflictSeverity(self.severity))
        object.__setattr__(self, "paths", tuple(sorted(self.paths, key=lambda item: (item.path, item.left_mode.value, item.right_mode.value))))

    @property
    def pair(self) -> tuple[str, str]:
        return (str(self.left), str(self.right))

    def involves(self, horizon_id: str | int) -> bool:
        wanted = HorizonId(horizon_id)
        return self.left == wanted or self.right == wanted

    def other(self, horizon_id: str | int) -> HorizonId:
        wanted = HorizonId(horizon_id)
        if self.left == wanted:
            return self.right
        if self.right == wanted:
            return self.left
        raise ValueError(f"{wanted} is not in conflict pair {self.left}/{self.right}")

    def to_dict(self) -> dict[str, object]:
        return {
            "left": str(self.left),
            "right": str(self.right),
            "kind": self.kind.value,
            "severity": self.severity.value,
            "paths": [path.to_dict() for path in self.paths],
            "explanation": self.explanation,
        }


@dataclass
class ConflictMatrix:
    conflicts: tuple[Conflict, ...]
    compatible_groups: tuple[tuple[HorizonId, ...], ...] = ()
    blockers_by_horizon: dict[HorizonId, tuple[Conflict, ...]] = field(default_factory=dict)
    schema_version: int = 1
    generated_from: str = ""

    def __post_init__(self) -> None:
        self.conflicts = tuple(sorted(self.conflicts, key=_conflict_sort_key))
        if not self.blockers_by_horizon:
            self.blockers_by_horizon = _build_blockers(self.conflicts)
        else:
            self.blockers_by_horizon = {
                HorizonId(horizon_id): tuple(sorted(conflicts, key=_conflict_sort_key))
                for horizon_id, conflicts in self.blockers_by_horizon.items()
            }
        self.compatible_groups = tuple(tuple(HorizonId(item) for item in group) for group in self.compatible_groups)

    @property
    def blocking_pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(conflict.pair for conflict in self.conflicts if conflict.severity is ConflictSeverity.BLOCK)

    def cannot_run_with(self, horizon_id: str | int) -> tuple[HorizonId, ...]:
        blockers = self.blockers_by_horizon.get(HorizonId(horizon_id), ())
        return tuple(sorted((conflict.other(horizon_id) for conflict in blockers), key=lambda item: item.number))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_from": self.generated_from,
            "conflict_count": len(self.conflicts),
            "blocking_pair_count": len(self.blocking_pairs),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "blockers_by_horizon": {
                str(horizon_id): [conflict.to_dict() for conflict in conflicts]
                for horizon_id, conflicts in sorted(self.blockers_by_horizon.items(), key=lambda item: item[0].number)
            },
            "cannot_run_with": {
                str(horizon_id): [str(other) for other in self.cannot_run_with(horizon_id)]
                for horizon_id in sorted(self.blockers_by_horizon, key=lambda item: item.number)
            },
            "compatible_groups": [[str(horizon_id) for horizon_id in group] for group in self.compatible_groups],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


def build_conflict_matrix(
    state: HorizonState,
    *,
    forbidden_paths: Iterable[str] | None = None,
) -> ConflictMatrix:
    """Build a deterministic conflict matrix from the H39 state model."""

    forbidden = tuple(sorted({_normalize_path(path) for path in (forbidden_paths or ()) if str(path).strip()}))
    conflicts: list[Conflict] = []
    records = tuple(state.records)
    for index, left in enumerate(records):
        conflicts.extend(_forbidden_conflicts(left, forbidden))
        for right in records[index + 1 :]:
            conflict = _classify_pair(left, right)
            if conflict is not None:
                conflicts.append(conflict)
    unique = _deduplicate_conflicts(conflicts)
    blockers = _build_blockers(unique)
    groups = _build_compatible_groups(records, blockers)
    return ConflictMatrix(
        conflicts=unique,
        compatible_groups=groups,
        blockers_by_horizon=blockers,
        generated_from=state.generated_from,
    )


def write_conflict_matrix(
    state: HorizonState,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    forbidden_paths: Iterable[str] | None = None,
) -> ConflictMatrix:
    matrix = build_conflict_matrix(state, forbidden_paths=forbidden_paths)
    matrix.write_json(output_path)
    return matrix


def _classify_pair(left: HorizonRecord, right: HorizonRecord) -> Conflict | None:
    overlaps = _overlapping_paths(left.owned_files, right.owned_files)
    if overlaps:
        kind = _path_conflict_kind(overlaps)
        severity = _path_conflict_severity(kind)
        path_list = ", ".join(path.path for path in overlaps[:3])
        suffix = "" if len(overlaps) <= 3 else f" and {len(overlaps) - 3} more"
        return Conflict(
            left=left.id,
            right=right.id,
            kind=kind,
            severity=severity,
            paths=tuple(overlaps),
            explanation=f"{left.id} and {right.id} both declare {path_list}{suffix}.",
        )

    if _has_dependency_order(left, right):
        return Conflict(
            left=left.id,
            right=right.id,
            kind=ConflictKind.DEPENDENCY_ORDER,
            severity=ConflictSeverity.INFO,
            explanation=f"{left.id} and {right.id} have an ordering dependency but no owned-file collision.",
        )
    return None


def _overlapping_paths(left: Iterable[OwnedPath], right: Iterable[OwnedPath]) -> list[ConflictPath]:
    overlaps: dict[tuple[str, str, str], ConflictPath] = {}
    for left_path in left:
        for right_path in right:
            overlap = _path_overlap(left_path.path, right_path.path)
            if overlap is None:
                continue
            key = (overlap, left_path.mode.value, right_path.mode.value)
            overlaps.setdefault(key, ConflictPath(overlap, left_path.mode, right_path.mode))
    return sorted(overlaps.values(), key=lambda item: (item.path, item.left_mode.value, item.right_mode.value))


def _path_overlap(left: str, right: str) -> str | None:
    left_norm = _normalize_path(left)
    right_norm = _normalize_path(right)
    if left_norm == right_norm:
        return left_norm
    if _glob_covers(left_norm, right_norm):
        return right_norm
    if _glob_covers(right_norm, left_norm):
        return left_norm
    return None


def _glob_covers(pattern: str, path: str) -> bool:
    if "**" in pattern:
        prefix = pattern.split("**", 1)[0].rstrip("/")
        return not prefix or path == prefix or path.startswith(prefix + "/")
    if pattern.endswith("/*"):
        prefix = pattern[:-2].rstrip("/")
        return path.startswith(prefix + "/") and "/" not in path[len(prefix) + 1 :]
    if pattern.endswith("*"):
        return path.startswith(pattern[:-1])
    return False


def _path_conflict_kind(paths: Iterable[ConflictPath]) -> ConflictKind:
    modes = {path.left_mode for path in paths} | {path.right_mode for path in paths}
    if OwnedPathMode.GENERATED in modes:
        return ConflictKind.GENERATED_ARTIFACT
    if OwnedPathMode.READ_ONLY in modes and any(_is_writer(mode) for mode in modes):
        return ConflictKind.READ_WRITE
    return ConflictKind.WRITE_WRITE


def _path_conflict_severity(kind: ConflictKind) -> ConflictSeverity:
    if kind in {ConflictKind.WRITE_WRITE, ConflictKind.GENERATED_ARTIFACT, ConflictKind.FORBIDDEN_FILE}:
        return ConflictSeverity.BLOCK
    if kind is ConflictKind.READ_WRITE:
        return ConflictSeverity.WARN
    return ConflictSeverity.INFO


def _is_writer(mode: OwnedPathMode) -> bool:
    return mode in {OwnedPathMode.EXCLUSIVE, OwnedPathMode.GENERATED, OwnedPathMode.UNKNOWN}


def _has_dependency_order(left: HorizonRecord, right: HorizonRecord) -> bool:
    left_deps = {dependency.id for dependency in left.dependencies}
    right_deps = {dependency.id for dependency in right.dependencies}
    return right.id in left_deps or left.id in right_deps


def _forbidden_conflicts(record: HorizonRecord, forbidden_paths: Iterable[str]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for forbidden in forbidden_paths:
        matched = [
            ConflictPath(_path_overlap(forbidden, owned.path) or _normalize_path(owned.path), OwnedPathMode.UNKNOWN, owned.mode)
            for owned in record.owned_files
            if _path_overlap(forbidden, owned.path) is not None
        ]
        if not matched:
            continue
        conflicts.append(
            Conflict(
                left=record.id,
                right=record.id,
                kind=ConflictKind.FORBIDDEN_FILE,
                severity=ConflictSeverity.BLOCK,
                paths=tuple(matched),
                explanation=f"{record.id} declares a forbidden path owned by policy: {forbidden}.",
            )
        )
    return conflicts


def _build_blockers(conflicts: Iterable[Conflict]) -> dict[HorizonId, tuple[Conflict, ...]]:
    blockers: dict[HorizonId, list[Conflict]] = {}
    for conflict in conflicts:
        if conflict.severity is not ConflictSeverity.BLOCK:
            continue
        blockers.setdefault(conflict.left, []).append(conflict)
        if conflict.right != conflict.left:
            blockers.setdefault(conflict.right, []).append(conflict)
    return {
        horizon_id: tuple(sorted(items, key=_conflict_sort_key))
        for horizon_id, items in sorted(blockers.items(), key=lambda item: item[0].number)
    }


def _build_compatible_groups(
    records: Iterable[HorizonRecord],
    blockers: dict[HorizonId, tuple[Conflict, ...]],
) -> tuple[tuple[HorizonId, ...], ...]:
    blocked_pairs = {
        frozenset((conflict.left, conflict.right))
        for conflict_list in blockers.values()
        for conflict in conflict_list
    }
    groups: list[tuple[HorizonId, ...]] = []
    current_wave: int | None = None
    current: list[HorizonId] = []
    for record in sorted(records, key=lambda item: ((item.wave or 10_000), item.id.number)):
        if current_wave != record.wave:
            if current:
                groups.append(tuple(current))
            current_wave = record.wave
            current = []
        if all(frozenset((record.id, other)) not in blocked_pairs for other in current):
            current.append(record.id)
        else:
            if current:
                groups.append(tuple(current))
            current = [record.id]
    if current:
        groups.append(tuple(current))
    return tuple(group for group in groups if group)


def _deduplicate_conflicts(conflicts: Iterable[Conflict]) -> tuple[Conflict, ...]:
    unique: dict[tuple[str, str, str, tuple[tuple[str, str, str], ...]], Conflict] = {}
    for conflict in conflicts:
        path_key = tuple((path.path, path.left_mode.value, path.right_mode.value) for path in conflict.paths)
        unique.setdefault((*conflict.pair, conflict.kind.value, path_key), conflict)
    return tuple(sorted(unique.values(), key=_conflict_sort_key))


def _conflict_sort_key(conflict: Conflict) -> tuple[int, int, str, str, tuple[str, ...]]:
    return (
        conflict.left.number,
        conflict.right.number,
        conflict.severity.value,
        conflict.kind.value,
        tuple(path.path for path in conflict.paths),
    )


def _normalize_path(path: str) -> str:
    return str(path).strip().strip("`").replace("\\", "/").rstrip("/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate horizon conflict matrix JSON.")
    parser.add_argument("--horizons-dir", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--forbidden-path",
        action="append",
        default=[],
        help="Path or glob that should produce a blocking policy conflict when declared.",
    )
    args = parser.parse_args(argv)

    from .parser import DEFAULT_HORIZONS_DIR, parse_horizon_tree

    state = parse_horizon_tree(args.horizons_dir or DEFAULT_HORIZONS_DIR)
    matrix = write_conflict_matrix(state, args.output, forbidden_paths=args.forbidden_path)
    print(
        f"wrote {args.output}: conflicts={len(matrix.conflicts)} "
        f"blocking_pairs={len(matrix.blocking_pairs)} groups={len(matrix.compatible_groups)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
