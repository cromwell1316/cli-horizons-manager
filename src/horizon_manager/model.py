"""Canonical horizon state model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from pathlib import Path
from typing import Any, Iterable


_HORIZON_ID_RE = re.compile(r"(?:HCO-)?H?(\d{1,3})", re.IGNORECASE)


class HorizonId(str):
    """Normalized HCO horizon id, for example ``H39``."""

    def __new__(cls, value: str | int) -> "HorizonId":
        if isinstance(value, int):
            number = value
        else:
            match = _HORIZON_ID_RE.search(str(value).strip())
            if not match:
                raise ValueError(f"invalid horizon id: {value!r}")
            number = int(match.group(1))
        return str.__new__(cls, f"H{number:02d}")

    @property
    def number(self) -> int:
        return int(self[1:])


class HorizonStatus(Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"

    @classmethod
    def normalize(cls, value: str | None) -> "HorizonStatus":
        text = (value or "").strip().lower().replace("-", "_")
        if not text:
            return cls.UNKNOWN
        if "in progress" in text or "in_progress" in text or "active" in text:
            return cls.IN_PROGRESS
        for status in cls:
            if status.value in text:
                return status
        return cls.UNKNOWN


class OwnedPathMode(Enum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    GENERATED = "generated"
    READ_ONLY = "read_only"
    UNKNOWN = "unknown"

    @classmethod
    def normalize(cls, value: str | None) -> "OwnedPathMode":
        text = (value or "").strip().lower().replace("-", "_")
        for mode in cls:
            if mode.value in text:
                return mode
        if "read only" in text:
            return cls.READ_ONLY
        return cls.UNKNOWN


@dataclass(frozen=True, order=True)
class HorizonDependency:
    id: HorizonId
    source: str
    raw: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", HorizonId(self.id))

    def to_dict(self) -> dict[str, str]:
        return {"id": str(self.id), "source": self.source, "raw": self.raw}


@dataclass(frozen=True, order=True)
class OwnedPath:
    path: str
    mode: OwnedPathMode = OwnedPathMode.UNKNOWN
    raw: str = ""
    section: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", str(self.path).strip())
        if isinstance(self.mode, str):
            object.__setattr__(self, "mode", OwnedPathMode.normalize(self.mode))

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "mode": self.mode.value,
            "raw": self.raw,
            "section": self.section,
        }


@dataclass(frozen=True, order=True)
class ParseWarning:
    code: str
    horizon_id: HorizonId | None
    message: str
    source_path: str = ""
    section: str = ""

    def __post_init__(self) -> None:
        if self.horizon_id is not None:
            object.__setattr__(self, "horizon_id", HorizonId(self.horizon_id))

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "horizon_id": str(self.horizon_id) if self.horizon_id else None,
            "message": self.message,
            "source_path": self.source_path,
            "section": self.section,
        }


@dataclass
class HorizonRecord:
    id: HorizonId
    title: str
    directory: str
    source_path: str
    status: HorizonStatus = HorizonStatus.UNKNOWN
    wave: int | None = None
    dates: tuple[str, ...] = ()
    dependencies: tuple[HorizonDependency, ...] = ()
    owned_files: tuple[OwnedPath, ...] = ()
    concurrency: str = ""
    warnings: tuple[ParseWarning, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = HorizonId(self.id)
        if isinstance(self.status, str):
            self.status = HorizonStatus.normalize(self.status)
        self.dependencies = tuple(sorted(self.dependencies, key=lambda d: (d.id.number, d.source, d.raw)))
        self.owned_files = tuple(sorted(self.owned_files, key=lambda p: (p.path, p.mode.value, p.section)))
        self.warnings = tuple(sorted(self.warnings, key=lambda w: (w.code, str(w.horizon_id), w.source_path, w.section, w.message)))
        self.dates = tuple(sorted(self.dates))
        self.metadata = _stable_value(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "title": self.title,
            "directory": self.directory,
            "source_path": self.source_path,
            "status": self.status.value,
            "wave": self.wave,
            "dates": list(self.dates),
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
            "owned_files": [owned.to_dict() for owned in self.owned_files],
            "concurrency": self.concurrency,
            "warnings": [warning.to_dict() for warning in self.warnings],
            "metadata": self.metadata,
        }


@dataclass
class HorizonState:
    records: tuple[HorizonRecord, ...]
    warnings: tuple[ParseWarning, ...] = ()
    schema_version: int = 1
    generated_from: str = ""

    def __post_init__(self) -> None:
        self.records = tuple(sorted(self.records, key=lambda r: r.id.number))
        record_warnings = tuple(w for record in self.records for w in record.warnings)
        self.warnings = tuple(sorted((*self.warnings, *record_warnings), key=_warning_sort_key))

    def __iter__(self) -> Iterable[HorizonRecord]:
        return iter(self.records)

    def get(self, horizon_id: str | int) -> HorizonRecord | None:
        wanted = HorizonId(horizon_id)
        for record in self.records:
            if record.id == wanted:
                return record
        return None

    def require(self, horizon_id: str | int) -> HorizonRecord:
        record = self.get(horizon_id)
        if record is None:
            raise KeyError(str(HorizonId(horizon_id)))
        return record

    def dependency_edges(self) -> list[dict[str, str]]:
        edges: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for record in self.records:
            for dependency in record.dependencies:
                key = (str(dependency.id), str(record.id), dependency.source)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"from": str(dependency.id), "to": str(record.id), "source": dependency.source})
        return sorted(edges, key=lambda edge: (_id_number(edge["from"]), _id_number(edge["to"]), edge["source"]))

    def owned_path_index(self) -> dict[str, list[dict[str, str]]]:
        index: dict[str, list[dict[str, str]]] = {}
        for record in self.records:
            for owned in record.owned_files:
                index.setdefault(owned.path, []).append(
                    {
                        "horizon_id": str(record.id),
                        "mode": owned.mode.value,
                        "section": owned.section,
                        "raw": owned.raw,
                    }
                )
        return {path: sorted(rows, key=lambda row: (_id_number(row["horizon_id"]), row["mode"], row["section"], row["raw"])) for path, rows in sorted(index.items())}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_from": self.generated_from,
            "horizon_count": len(self.records),
            "horizons": [record.to_dict() for record in self.records],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "dependency_edges": self.dependency_edges(),
            "owned_path_index": self.owned_path_index(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


def _id_number(value: str) -> int:
    return HorizonId(value).number


def _warning_sort_key(warning: ParseWarning) -> tuple[str, int, str, str, str]:
    horizon_number = warning.horizon_id.number if warning.horizon_id else 0
    return (warning.code, horizon_number, warning.source_path, warning.section, warning.message)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    return value
