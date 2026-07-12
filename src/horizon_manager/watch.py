"""Horizon Manager file watcher contracts.

The watcher is intentionally small and deterministic: filesystem adapters produce
``WatchEvent`` values, this module classifies them into a refresh request, and a
backend decides how to deliver that request to the daemon or CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib import request as urlrequest

from .events import EventSeverity, EventType, HorizonEvent, append_event


@dataclass(frozen=True)
class WatchConfig:
    watched_roots: tuple[Path, ...]
    daemon_endpoint: str = "http://127.0.0.1:8765"
    debounce_ms: int = 250
    render_targets: tuple[str, ...] = ("dashboard", "dag", "history")
    event_log_path: Path | None = None
    actor: str = "horizon-watch"
    corpora: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        roots = tuple(Path(root) for root in self.watched_roots)
        if self.corpora:
            roots = tuple(sorted((*roots, *registered_corpus_watch_roots(self.corpora)), key=lambda item: item.as_posix()))
        object.__setattr__(self, "watched_roots", roots)
        object.__setattr__(self, "render_targets", tuple(sorted(str(target) for target in self.render_targets)))
        object.__setattr__(self, "corpora", tuple(sorted(self.corpora, key=lambda item: _corpus_name(item))))
        if self.event_log_path is not None:
            object.__setattr__(self, "event_log_path", Path(self.event_log_path))
        if self.debounce_ms < 0:
            raise ValueError("debounce_ms must be non-negative")
        if not self.actor.strip():
            raise ValueError("actor is required")


@dataclass(frozen=True)
class WatchEvent:
    path: Path
    kind: str
    timestamp_ms: int
    reason: str = "filesystem"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "kind", str(self.kind).strip().lower() or "modified")
        object.__setattr__(self, "timestamp_ms", int(self.timestamp_ms))
        object.__setattr__(self, "reason", str(self.reason).strip() or "filesystem")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": _display_path(self.path),
            "reason": self.reason,
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass(frozen=True)
class RefreshRequest:
    refresh_state: bool = False
    refresh_dashboard: bool = False
    refresh_dag: bool = False
    refresh_history: bool = False
    refresh_preflight: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)
    changed_paths: tuple[str, ...] = field(default_factory=tuple)
    event_count: int = 0
    max_timestamp_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(sorted({str(reason) for reason in self.reasons if str(reason)})))
        object.__setattr__(self, "changed_paths", tuple(sorted({str(path) for path in self.changed_paths if str(path)})))
        object.__setattr__(self, "event_count", int(self.event_count))
        object.__setattr__(self, "max_timestamp_ms", int(self.max_timestamp_ms))

    @property
    def targets(self) -> tuple[str, ...]:
        targets = []
        if self.refresh_state:
            targets.append("state")
        if self.refresh_dashboard:
            targets.append("dashboard")
        if self.refresh_dag:
            targets.append("dag")
        if self.refresh_history:
            targets.append("history")
        if self.refresh_preflight:
            targets.append("preflight")
        return tuple(targets)

    @property
    def has_work(self) -> bool:
        return bool(self.targets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_paths": list(self.changed_paths),
            "event_count": self.event_count,
            "max_timestamp_ms": self.max_timestamp_ms,
            "reasons": list(self.reasons),
            "targets": list(self.targets),
        }


RefreshPlan = RefreshRequest


@dataclass(frozen=True)
class CorpusRefreshPlan:
    corpus: dict[str, str]
    request: RefreshRequest

    def __post_init__(self) -> None:
        object.__setattr__(self, "corpus", _stable_value(self.corpus))

    @property
    def has_work(self) -> bool:
        return self.request.has_work

    def to_dict(self) -> dict[str, Any]:
        return {"corpus": self.corpus, "request": self.request.to_dict()}


@dataclass(frozen=True)
class DaemonRefreshCommand:
    method: str
    url: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", self.method.upper())
        object.__setattr__(self, "url", str(self.url))
        object.__setattr__(self, "payload", _stable_value(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {"method": self.method, "payload": self.payload, "url": self.url}


class WatchBackend(Protocol):
    def events(self, config: WatchConfig) -> list[WatchEvent]:
        ...

    def request_refresh(self, plan: RefreshRequest) -> None:
        ...


class SnapshotWatchBackend:
    """Portable polling backend based on stable file metadata snapshots."""

    def __init__(self, snapshot: dict[str, tuple[int, int]] | None = None) -> None:
        self.snapshot = dict(snapshot or {})

    def events(self, config: WatchConfig) -> list[WatchEvent]:
        current = snapshot_watch_paths(config.watched_roots)
        timestamp = _snapshot_timestamp(current)
        events: list[WatchEvent] = []
        for path in sorted(set(current) | set(self.snapshot)):
            if path not in self.snapshot:
                events.append(WatchEvent(Path(path), "created", timestamp, "snapshot"))
            elif path not in current:
                events.append(WatchEvent(Path(path), "deleted", timestamp, "snapshot"))
            elif current[path] != self.snapshot[path]:
                events.append(WatchEvent(Path(path), "modified", timestamp, "snapshot"))
        self.snapshot = current
        return events

    def request_refresh(self, plan: RefreshRequest) -> None:
        del plan


class DaemonRefreshBackend(SnapshotWatchBackend):
    """Snapshot backend that can deliver refresh commands to the H51 daemon."""

    def __init__(self, config: WatchConfig, snapshot: dict[str, tuple[int, int]] | None = None) -> None:
        super().__init__(snapshot)
        self.config = config

    def request_refresh(self, plan: RefreshRequest) -> None:
        for command in daemon_refresh_commands(plan, self.config):
            _send_daemon_command(command)


HORIZON_DIR_CANONICAL_NAME = "horizons"
HORIZON_DIR_ALIAS_NAMES = frozenset({"horizonts"})
_HORIZON_DIR_NAMES = frozenset({HORIZON_DIR_CANONICAL_NAME, *HORIZON_DIR_ALIAS_NAMES})


def classify_change(path: str | Path) -> RefreshRequest:
    """Return the refresh work implied by a changed file path."""

    text = _display_path(path)
    name = Path(text).name
    reasons: list[str] = []
    state = dashboard = dag = history = preflight = False
    if _is_generated_render_output(text):
        return RefreshRequest(reasons=("render-output",), changed_paths=(text,))
    if _has_horizon_dir_segment(text) and _is_horizon_document(name):
        state = dashboard = dag = history = True
        reasons.append("horizon-document")
    if name in {"horizon_locks.json", "horizon_events.jsonl"}:
        state = dashboard = True
        reasons.append("coordination-state")
    if name.startswith("horizon_") and name.endswith(".json") and name != "horizon_locks.json":
        state = dashboard = True
        reasons.append("generated-state")
    if text == "git-status" or text.endswith("/.git/index"):
        preflight = True
        reasons.append("git-status")
    return RefreshRequest(state, dashboard, dag, history, preflight, tuple(reasons), (text,))


def debounce_events(events: list[WatchEvent], window_ms: int) -> list[WatchEvent]:
    """Coalesce repeated path events inside deterministic debounce windows."""

    if not events:
        return []
    sorted_events = sorted(events, key=lambda event: (event.timestamp_ms, str(event.path)))
    selected: list[tuple[Path, int, WatchEvent]] = []
    for event in sorted_events:
        path = Path(_display_path(event.path))
        for index, (bucket_path, bucket_start, _bucket_event) in enumerate(selected):
            if bucket_path == path and event.timestamp_ms - bucket_start <= window_ms:
                selected[index] = (bucket_path, bucket_start, event)
                break
        else:
            selected.append((path, event.timestamp_ms, event))
    return [event for _path, _start, event in sorted(selected, key=lambda item: (item[2].timestamp_ms, str(item[2].path), item[2].kind))]


def merge_plans(plans: list[RefreshRequest]) -> RefreshRequest:
    reasons = sorted({reason for plan in plans for reason in plan.reasons})
    paths = sorted({path for plan in plans for path in plan.changed_paths})
    return RefreshRequest(
        refresh_state=any(plan.refresh_state for plan in plans),
        refresh_dashboard=any(plan.refresh_dashboard for plan in plans),
        refresh_dag=any(plan.refresh_dag for plan in plans),
        refresh_history=any(plan.refresh_history for plan in plans),
        refresh_preflight=any(plan.refresh_preflight for plan in plans),
        reasons=tuple(reasons),
        changed_paths=tuple(paths),
        event_count=sum(plan.event_count for plan in plans),
        max_timestamp_ms=max((plan.max_timestamp_ms for plan in plans), default=0),
    )


def plan_refresh(events: Iterable[WatchEvent], *, window_ms: int = 250) -> RefreshRequest:
    """Build the deterministic refresh request for an event sequence."""

    debounced = debounce_events(list(events), window_ms)
    plans: list[RefreshRequest] = []
    for event in debounced:
        plan = classify_change(event.path)
        plans.append(
            RefreshRequest(
                refresh_state=plan.refresh_state,
                refresh_dashboard=plan.refresh_dashboard,
                refresh_dag=plan.refresh_dag,
                refresh_history=plan.refresh_history,
                refresh_preflight=plan.refresh_preflight,
                reasons=(*plan.reasons, event.reason),
                changed_paths=plan.changed_paths,
                event_count=1,
                max_timestamp_ms=event.timestamp_ms,
            )
        )
    return merge_plans(plans)


def plan_corpus_refresh(events: Iterable[WatchEvent], corpora: Iterable[Any], *, window_ms: int = 250) -> tuple[CorpusRefreshPlan, ...]:
    """Build deterministic refresh plans scoped to registered corpora."""

    debounced = debounce_events(list(events), window_ms)
    plans: list[CorpusRefreshPlan] = []
    for corpus in sorted(tuple(corpora), key=lambda item: _corpus_name(item)):
        scoped_events = tuple(_event_for_corpus(event, corpus) for event in debounced)
        scoped_events = tuple(event for event in scoped_events if event is not None)
        request = plan_refresh(scoped_events, window_ms=0)
        if request.has_work:
            plans.append(CorpusRefreshPlan(_corpus_metadata(corpus), request))
    return tuple(plans)


def run_watch_loop(config: WatchConfig, backend: WatchBackend) -> RefreshRequest:
    """Process one injectable backend batch for deterministic tests."""

    request = plan_refresh(backend.events(config), window_ms=config.debounce_ms)
    if request.has_work:
        backend.request_refresh(request)
        if config.event_log_path is not None:
            record_refresh_event(config.event_log_path, request, actor=config.actor)
    return request


def daemon_refresh_commands(request: RefreshRequest, config: WatchConfig) -> tuple[DaemonRefreshCommand, ...]:
    """Return deterministic HTTP commands needed to satisfy a refresh request."""

    base = config.daemon_endpoint.rstrip("/")
    commands: list[DaemonRefreshCommand] = []
    if request.refresh_state or request.refresh_preflight:
        commands.append(DaemonRefreshCommand("GET", f"{base}/state"))
    if request.refresh_dashboard or request.refresh_dag or request.refresh_history:
        commands.append(DaemonRefreshCommand("POST", f"{base}/render", request.to_dict()))
    return tuple(commands)


def record_refresh_event(path: str | Path, request: RefreshRequest, *, actor: str = "horizon-watch") -> HorizonEvent:
    """Append a deterministic H44 event describing a watcher refresh request."""

    event = HorizonEvent(
        event_id=_event_id(request),
        ts=_timestamp_from_ms(request.max_timestamp_ms),
        actor=actor,
        event_type=EventType.DAEMON,
        severity=EventSeverity.INFO,
        message="watch refresh requested",
        source="horizon_manager.watch",
        detail=request.to_dict(),
    )
    return append_event(path, event)


def snapshot_watch_paths(roots: Iterable[str | Path]) -> dict[str, tuple[int, int]]:
    """Return deterministic file metadata for watcher-relevant paths."""

    snapshot: dict[str, tuple[int, int]] = {}
    for root in sorted((Path(item) for item in roots), key=lambda item: str(item)):
        if root.is_file():
            candidates = (root,)
        elif root.exists():
            candidates = tuple(path for path in root.rglob("*") if path.is_file())
        else:
            candidates = ()
        for path in candidates:
            text = _display_path(path)
            if classify_change(text).reasons:
                stat = path.stat()
                snapshot[text] = (stat.st_mtime_ns, stat.st_size)
    return {key: snapshot[key] for key in sorted(snapshot)}


def registered_corpus_watch_roots(corpora: Iterable[Any]) -> tuple[Path, ...]:
    """Return stable root directories for all registered corpora."""

    roots = []
    for corpus in corpora:
        roots.append(Path(_corpus_field(corpus, "repo_root")))
    return tuple(sorted({root for root in roots}, key=lambda item: item.as_posix()))


def _is_horizon_document(name: str) -> bool:
    return name == "README.md" or (name.endswith(".md") and (name.startswith("H_") or name.startswith("V_")))


def _has_horizon_dir_segment(path: str) -> bool:
    return any(part in _HORIZON_DIR_NAMES for part in path.split("/"))


def _is_generated_render_output(text: str) -> bool:
    name = Path(text).name
    return name in {"horizon_dashboard.html", "horizon_dependency_graph.html"} or (
        name.endswith(".html") and ("dashboard" in name or "dependency_graph" in name)
    )


def _display_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _event_for_corpus(event: WatchEvent, corpus: Any) -> WatchEvent | None:
    path = Path(event.path)
    repo_root = Path(_corpus_field(corpus, "repo_root"))
    horizons_dir = Path(_corpus_field(corpus, "horizons_dir"))
    generated_dir = Path(_corpus_field(corpus, "generated_dir"))
    relative = _relative_to_any(path, (repo_root, horizons_dir, generated_dir))
    if relative is None:
        return None
    return WatchEvent(relative, event.kind, event.timestamp_ms, event.reason)


def _relative_to_any(path: Path, roots: Iterable[Path]) -> Path | None:
    for root in sorted((Path(item) for item in roots), key=lambda item: len(item.as_posix()), reverse=True):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if root.name in _HORIZON_DIR_NAMES:
            return Path(root.name) / relative
        if root.name == "management":
            return Path("management") / relative
        return relative
    return path if not path.is_absolute() else None


def _corpus_metadata(corpus: Any) -> dict[str, str]:
    return {
        "name": _corpus_name(corpus),
        "title": _corpus_field(corpus, "title"),
        "repo_root": _corpus_field(corpus, "repo_root"),
        "horizons_dir": _corpus_field(corpus, "horizons_dir"),
        "generated_dir": _corpus_field(corpus, "generated_dir"),
    }


def _corpus_name(corpus: Any) -> str:
    return _corpus_field(corpus, "name")


def _corpus_field(corpus: Any, field: str) -> str:
    if isinstance(corpus, dict):
        return str(corpus.get(field, ""))
    return str(getattr(corpus, field))


def _event_id(request: RefreshRequest) -> str:
    payload = json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"))
    return "watch-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _timestamp_from_ms(timestamp_ms: int) -> str:
    if timestamp_ms <= 0:
        return datetime.fromtimestamp(0, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _snapshot_timestamp(snapshot: dict[str, tuple[int, int]]) -> int:
    if not snapshot:
        return 0
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _send_daemon_command(command: DaemonRefreshCommand) -> None:
    payload = json.dumps(command.payload, sort_keys=True).encode("utf-8")
    req = urlrequest.Request(command.url, data=payload if command.method != "GET" else None, method=command.method)
    req.add_header("Content-Type", "application/json")
    with urlrequest.urlopen(req, timeout=5) as response:  # nosec B310 - localhost endpoint is caller-configured.
        response.read()


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    json.dumps(value, sort_keys=True)
    return value
