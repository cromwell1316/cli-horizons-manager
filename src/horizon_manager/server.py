"""Local Horizon Manager daemon contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import RLock
from typing import Any

from .conflicts import build_conflict_matrix
from .doctor import run_doctor
from .events import read_events
from .locks import LockSnapshot, LockStore, claim_horizon, release_horizon
from .next import recommend_next
from .parser import parse_horizon_tree


READ_ENDPOINTS = {
    "/metadata": "metadata",
    "/state": "state",
    "/doctor": "doctor",
    "/conflicts": "conflicts",
    "/locks": "locks",
    "/next": "next",
    "/events": "events",
    "/dashboard": "dashboard",
}
WRITE_ENDPOINTS = {"/claim", "/release", "/render"}


@dataclass(frozen=True)
class DaemonConfig:
    """Project-local daemon configuration."""

    corpus_path: Path
    generated_dir: Path
    corpus_name: str = "custom"
    corpus_title: str = "Custom horizon corpus"
    repo_root: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8765
    readonly: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "corpus_path", Path(self.corpus_path))
        object.__setattr__(self, "generated_dir", Path(self.generated_dir))
        object.__setattr__(self, "repo_root", Path(self.repo_root) if self.repo_root is not None else _default_repo_root(Path(self.generated_dir)))
        object.__setattr__(self, "corpus_name", str(self.corpus_name).strip() or "custom")
        object.__setattr__(self, "corpus_title", str(self.corpus_title).strip() or str(self.corpus_name))

    def validate(self) -> None:
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Horizon Manager daemon must bind localhost by default")

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "corpus": self.corpus_name,
            "title": self.corpus_title,
            "repo_root": str(self.repo_root),
            "horizons_dir": str(self.corpus_path),
            "generated_dir": str(self.generated_dir),
        }


@dataclass
class DaemonState:
    """Cached Horizon Manager state bundle."""

    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[str] = field(default_factory=list)
    revision: str = "manual"
    claimed: dict[str, str] = field(default_factory=dict)
    config: DaemonConfig | None = None
    horizon_state: Any = None
    doctor_report: Any = None
    conflict_matrix: Any = None
    lock_snapshot: LockSnapshot = field(default_factory=LockSnapshot)
    next_report: Any = None
    mutex: RLock = field(default_factory=RLock, repr=False, compare=False)

    def sync_data(self) -> None:
        if self.config is not None:
            self.data["metadata"] = self.config.metadata
        if self.horizon_state is not None:
            self.data["state"] = self.horizon_state.to_dict()
        if self.doctor_report is not None:
            self.data["doctor"] = self.doctor_report.to_dict()
        if self.conflict_matrix is not None:
            self.data["conflicts"] = self.conflict_matrix.to_dict()
        self.data["locks"] = self.lock_snapshot.to_dict()
        if self.next_report is not None:
            self.data["next"] = self.next_report.to_dict()


@dataclass(frozen=True)
class DaemonRequest:
    method: str
    path: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class DaemonResponse:
    ok: bool
    data: Any = None
    diagnostics: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": _stable_value(self.data),
            "diagnostics": list(self.diagnostics),
            "error": self.error,
        }


def ok(data: Any, diagnostics: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    return DaemonResponse(True, data, tuple(diagnostics or ())).to_dict()


def fail(message: str, diagnostics: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    return DaemonResponse(False, None, tuple(diagnostics or ()), message).to_dict()


def refresh_state(config: DaemonConfig) -> DaemonState:
    """Build a deterministic state bundle from modules and generated files."""

    config.validate()
    diagnostics: list[str] = []
    bundle: dict[str, Any] = {"metadata": config.metadata, "corpus_path": str(config.corpus_path)}

    try:
        horizon_state = parse_horizon_tree(config.corpus_path)
        doctor_report = run_doctor(horizon_state, repo_root=_repo_root(config), generated_paths=_generated_files(config))
        conflict_matrix = build_conflict_matrix(horizon_state)
        lock_snapshot = LockStore(config.generated_dir / "horizon_locks.json").load()
        next_report = recommend_next(horizon_state, doctor_report, conflict_matrix, lock_snapshot)
    except Exception as exc:
        horizon_state = None
        doctor_report = None
        conflict_matrix = None
        lock_snapshot = LockSnapshot()
        next_report = None
        diagnostics.append(f"refresh_error:{exc}")

    state = DaemonState(
        data=bundle,
        diagnostics=diagnostics,
        revision=_revision(config),
        config=config,
        horizon_state=horizon_state,
        doctor_report=doctor_report,
        conflict_matrix=conflict_matrix,
        lock_snapshot=lock_snapshot,
        next_report=next_report,
    )
    state.sync_data()
    _load_generated_sidecars(config, state)
    return state


def handle_request(
    request: DaemonRequest,
    state: DaemonState,
    *,
    readonly: bool = True,
) -> dict[str, Any]:
    """Route a request object without depending on the HTTP server."""

    method = request.method.upper()
    path = request.path.split("?", 1)[0].rstrip("/") or "/"
    if method == "GET" and path in READ_ENDPOINTS:
        key = READ_ENDPOINTS[path]
        return ok(state.data.get(key, {}), state.diagnostics)
    if method != "POST" or path not in WRITE_ENDPOINTS:
        return fail(f"unsupported route: {method} {path}")
    if readonly:
        return fail("mutating endpoint disabled in readonly mode")
    payload = request.payload or {}
    if path == "/claim":
        return _handle_claim(payload, state)
    if path == "/release":
        return _handle_release(payload, state)
    if path == "/render":
        return _handle_render(payload, state)
    return fail(f"unsupported route: {method} {path}")


def serve(config: DaemonConfig) -> ThreadingHTTPServer:
    """Create a localhost HTTP server."""

    config.validate()
    state = refresh_state(config)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, response: dict[str, Any]) -> None:
            status = 200 if response["ok"] else 400
            payload = json.dumps(response, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            self._send(handle_request(DaemonRequest("GET", self.path), state))

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError as exc:
                self._send(fail(f"invalid JSON payload: {exc}"))
                return
            self._send(handle_request(DaemonRequest("POST", self.path, payload), state, readonly=config.readonly))

        def log_message(self, format: str, *args: Any) -> None:
            return

    return ThreadingHTTPServer((config.host, config.port), Handler)


def _handle_claim(payload: dict[str, Any], state: DaemonState) -> dict[str, Any]:
    error = _require_payload(payload, "horizon", "owner")
    if error:
        return fail(error)
    horizon = str(payload["horizon"])
    owner = str(payload["owner"])
    ttl = int(payload.get("ttl", payload.get("ttl_seconds", 7200)))
    with state.mutex:
        if state.horizon_state is not None:
            next_snapshot, decision = claim_horizon(
                state.horizon_state,
                state.conflict_matrix,
                state.lock_snapshot,
                horizon,
                owner,
                ttl,
            )
            state.lock_snapshot = next_snapshot
            state.sync_data()
            _save_locks(state)
            response = decision.to_dict()
            if decision.ok:
                return ok(response, decision.warnings)
            return fail("claim rejected", decision.blockers)

        existing = state.claimed.get(horizon)
        if existing and existing != owner:
            return fail(f"{horizon} already claimed by {existing}", (f"lock:{existing}",))
        state.claimed[horizon] = owner
        return ok({"horizon": horizon, "owner": owner})


def _handle_release(payload: dict[str, Any], state: DaemonState) -> dict[str, Any]:
    error = _require_payload(payload, "horizon", "owner")
    if error:
        return fail(error)
    horizon = str(payload["horizon"])
    owner = str(payload["owner"])
    with state.mutex:
        if state.horizon_state is not None:
            next_snapshot, decision = release_horizon(state.lock_snapshot, horizon, owner)
            state.lock_snapshot = next_snapshot
            state.sync_data()
            _save_locks(state)
            response = decision.to_dict()
            if decision.ok:
                return ok(response, decision.warnings)
            return fail("release rejected", decision.blockers)

        if state.claimed.get(horizon) != owner:
            return fail(f"{horizon} is not claimed by {owner}", (f"not_claimed:{horizon}",))
        del state.claimed[horizon]
        return ok({"horizon": horizon, "released": True})


def _handle_render(payload: dict[str, Any], state: DaemonState) -> dict[str, Any]:
    del payload
    if state.config is None:
        return fail("render requires daemon config")
    written: list[str] = []
    with state.mutex:
        try:
            if state.horizon_state is not None:
                from .render import build_dashboard_model, render_dashboard, write_dashboard

                events = state.data.get("events", [])
                model = build_dashboard_model(
                    state.horizon_state,
                    state.doctor_report,
                    state.conflict_matrix,
                    state.lock_snapshot,
                    state.next_report,
                    events,
                )
                dashboard_path = state.config.generated_dir / "horizon_dashboard.html"
                write_dashboard(dashboard_path, render_dashboard(model))
                state.data["dashboard"] = dashboard_path.read_text(encoding="utf-8")
                written.append(str(dashboard_path))

                from .dag_render import build_dag_model, render_dag_html, write_dag

                dag_path = state.config.generated_dir / "horizon_dependency_graph.html"
                write_dag(dag_path, render_dag_html(build_dag_model(state.horizon_state, state.conflict_matrix, state.lock_snapshot)))
                written.append(str(dag_path))
        except Exception as exc:
            return fail(f"render failed: {exc}")
    return ok({"written": written})


def _load_generated_sidecars(config: DaemonConfig, state: DaemonState) -> None:
    for name in ("state", "doctor", "conflicts", "locks", "next"):
        path = config.generated_dir / f"horizon_{name}.json"
        if path.exists():
            try:
                state.data[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                state.diagnostics.append(f"invalid:{path.name}:{exc}")
        elif name not in state.data:
            state.diagnostics.append(f"missing:{path.name}")
            state.data[name] = {}

    events_path = config.generated_dir / "horizon_events.jsonl"
    if events_path.exists():
        try:
            state.data["events"] = [event.to_dict() for event in read_events(events_path)]
        except ValueError as exc:
            state.diagnostics.append(f"invalid:{events_path.name}:{exc}")
            state.data["events"] = []
    else:
        state.diagnostics.append(f"missing:{events_path.name}")
        state.data["events"] = []

    dashboard_path = config.generated_dir / "horizon_dashboard.html"
    state.data["dashboard"] = dashboard_path.read_text(encoding="utf-8") if dashboard_path.exists() else ""
    if not dashboard_path.exists():
        state.diagnostics.append(f"missing:{dashboard_path.name}")


def _require_payload(payload: dict[str, Any] | None, *keys: str) -> str | None:
    if payload is None:
        return "missing JSON payload"
    missing = [key for key in keys if not payload.get(key)]
    if missing:
        return "missing required field(s): " + ", ".join(missing)
    return None


def _save_locks(state: DaemonState) -> None:
    if state.config is not None:
        LockStore(state.config.generated_dir / "horizon_locks.json").save(state.lock_snapshot)


def _generated_files(config: DaemonConfig) -> tuple[str, ...]:
    root = _repo_root(config)
    paths = sorted(config.generated_dir.glob("horizon_*.json*"))
    return tuple(str(path.relative_to(root)) if path.is_relative_to(root) else str(path) for path in paths)


def _repo_root(config: DaemonConfig) -> Path:
    assert config.repo_root is not None
    return config.repo_root


def _default_repo_root(generated_dir: Path) -> Path:
    return generated_dir.parents[2] if len(generated_dir.parents) >= 3 else generated_dir


def _revision(config: DaemonConfig) -> str:
    values: list[str] = []
    for path in sorted(config.generated_dir.glob("horizon_*")):
        if path.is_file():
            stat = path.stat()
            values.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    return value
