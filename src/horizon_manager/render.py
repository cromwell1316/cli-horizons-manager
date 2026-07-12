"""Self-contained Horizon Manager dashboard renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable

from .model import HorizonId, HorizonRecord, HorizonState, HorizonStatus


DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "hermes-consistency-orchestrator/horizon_dashboard.html"
THEMES = frozenset({"auto", "light", "dark"})


@dataclass(frozen=True)
class TimelineItem:
    ts: str
    horizon_id: str
    event_type: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "ts": self.ts,
            "horizon_id": self.horizon_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class DashboardSection:
    section_id: str
    title: str
    rows: tuple[dict[str, Any], ...] = ()
    summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rows", tuple(_stable_value(row) for row in self.rows))
        object.__setattr__(self, "summary", _stable_value(self.summary))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.section_id, "title": self.title, "summary": self.summary, "rows": list(self.rows)}


@dataclass(frozen=True)
class DashboardModel:
    overview: dict[str, Any]
    board: tuple[dict[str, Any], ...]
    next_recommendations: tuple[dict[str, Any], ...] = ()
    blocked_horizons: tuple[dict[str, Any], ...] = ()
    conflict_summary: dict[str, Any] = field(default_factory=dict)
    active_locks: tuple[dict[str, Any], ...] = ()
    timeline: tuple[TimelineItem, ...] = ()
    sections: tuple[DashboardSection, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "overview", _stable_value(self.overview))
        object.__setattr__(self, "board", tuple(sorted((_stable_value(row) for row in self.board), key=lambda row: _id_number(row["horizon_id"]))))
        object.__setattr__(self, "next_recommendations", tuple(_stable_value(row) for row in self.next_recommendations))
        object.__setattr__(self, "blocked_horizons", tuple(_stable_value(row) for row in self.blocked_horizons))
        object.__setattr__(self, "conflict_summary", _stable_value(self.conflict_summary))
        object.__setattr__(self, "active_locks", tuple(_stable_value(row) for row in self.active_locks))
        object.__setattr__(self, "timeline", tuple(sorted(self.timeline, key=lambda item: (item.ts, item.horizon_id, item.event_type, item.message))))
        if not self.sections:
            object.__setattr__(self, "sections", _default_sections(self))

    def to_dict(self) -> dict[str, Any]:
        return {
            "overview": self.overview,
            "board": list(self.board),
            "next_recommendations": list(self.next_recommendations),
            "blocked_horizons": list(self.blocked_horizons),
            "conflict_summary": self.conflict_summary,
            "active_locks": list(self.active_locks),
            "timeline": [item.to_dict() for item in self.timeline],
            "sections": [section.to_dict() for section in self.sections],
        }


def build_dashboard_model(
    state: HorizonState | dict[str, Any],
    doctor: Any = None,
    conflicts: Any = None,
    locks: Any = None,
    next_report: Any = None,
    events: Iterable[Any] | None = None,
) -> DashboardModel:
    records = _records(state)
    event_rows = tuple(events or ())
    overview = _overview(records, doctor, conflicts, locks, next_report, event_rows)
    board = tuple(_board_row(record, doctor) for record in records)
    return DashboardModel(
        overview=overview,
        board=board,
        next_recommendations=_recommendations(next_report),
        blocked_horizons=_blocked_horizons(records, doctor),
        conflict_summary=_conflict_summary(conflicts),
        active_locks=_active_locks(locks),
        timeline=_timeline(event_rows),
    )


def render_dashboard(model: DashboardModel | dict[str, Any], theme: str = "auto") -> str:
    if theme not in THEMES:
        raise ValueError(f"unsupported theme: {theme!r}")
    model_dict = model.to_dict() if isinstance(model, DashboardModel) else _stable_value(model)
    html = [
        "<!doctype html>",
        '<html lang="en" data-theme="' + theme + '">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Horizon Mission Control</title>",
        "<style>",
        _css(),
        "</style>",
        "</head>",
        "<body>",
        '<main id="dashboard" class="dashboard">',
        '<header class="topbar"><div><p class="eyebrow">Horizon Manager</p><h1>Horizon Mission Control</h1></div><button id="theme-toggle" type="button">Theme</button></header>',
        _overview_html(model_dict["overview"]),
        _board_html(model_dict["board"]),
        _table_section("next", "Next Recommendations", model_dict["next_recommendations"], ("rank", "horizon_id", "title", "explanation")),
        _table_section("blocked", "Blocked Horizons", model_dict["blocked_horizons"], ("horizon_id", "title", "diagnostics")),
        _summary_section("conflicts", "Conflict Summary", model_dict["conflict_summary"]),
        _table_section("locks", "Active Locks", model_dict["active_locks"], ("horizon_id", "agent_id", "status", "expires_at")),
        _timeline_html(model_dict["timeline"]),
        "</main>",
        "<script>",
        _js(),
        "</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html) + "\n"


def write_dashboard(path: str | Path, html: str) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return html


def write_default_dashboard(
    state: HorizonState,
    *,
    doctor: Any = None,
    conflicts: Any = None,
    locks: Any = None,
    next_report: Any = None,
    events: Iterable[Any] | None = None,
    output_path: str | Path = DEFAULT_OUTPUT,
    theme: str = "auto",
) -> DashboardModel:
    model = build_dashboard_model(state, doctor, conflicts, locks, next_report, events)
    write_dashboard(output_path, render_dashboard(model, theme=theme))
    return model


def _records(state: HorizonState | dict[str, Any]) -> tuple[HorizonRecord | dict[str, Any], ...]:
    if isinstance(state, HorizonState):
        return tuple(state.records)
    return tuple(state.get("horizons", state.get("records", ())))


def _overview(records: tuple[Any, ...], doctor: Any, conflicts: Any, locks: Any, next_report: Any, events: Iterable[Any] | None) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for record in records:
        status = _status(record)
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "horizon_count": len(records),
        "status_counts": {key: statuses[key] for key in sorted(statuses)},
        "doctor_errors": _doctor_error_count(doctor),
        "blocking_conflicts": _blocking_conflict_count(conflicts),
        "active_locks": len(_active_locks(locks)),
        "recommendations": len(_recommendations(next_report)),
        "events": len(tuple(events or ())),
    }


def _board_row(record: HorizonRecord | dict[str, Any], doctor: Any) -> dict[str, Any]:
    horizon_id = _record_field(record, "id")
    return {
        "horizon_id": str(horizon_id),
        "title": str(_record_field(record, "title")),
        "status": _status(record),
        "wave": _record_field(record, "wave"),
        "diagnostics": len(_diagnostics_for(doctor, horizon_id)),
    }


def _recommendations(next_report: Any) -> tuple[dict[str, Any], ...]:
    if next_report is None:
        return ()
    data = _to_dict(next_report)
    rows = data.get("recommendations", ())
    return tuple(_stable_value(row) for row in rows)


def _blocked_horizons(records: tuple[Any, ...], doctor: Any) -> tuple[dict[str, Any], ...]:
    rows = []
    for record in records:
        diagnostics = _diagnostics_for(doctor, _record_field(record, "id"))
        errors = [item for item in diagnostics if item.get("severity") in {"error", "block", "critical", "fatal"}]
        if errors:
            rows.append(
                {
                    "horizon_id": str(_record_field(record, "id")),
                    "title": str(_record_field(record, "title")),
                    "diagnostics": len(errors),
                }
            )
    return tuple(sorted(rows, key=lambda row: _id_number(row["horizon_id"])))


def _conflict_summary(conflicts: Any) -> dict[str, Any]:
    if conflicts is None:
        return {"conflict_count": 0, "blocking_pair_count": 0}
    data = _to_dict(conflicts)
    return {
        "conflict_count": data.get("conflict_count", len(data.get("conflicts", ()))),
        "blocking_pair_count": data.get("blocking_pair_count", len(data.get("blocking_pairs", ()))),
    }


def _active_locks(locks: Any) -> tuple[dict[str, Any], ...]:
    if locks is None:
        return ()
    data = _to_dict(locks)
    rows = data.get("locks", data.get("active_locks", ()))
    active = [row for row in rows if row.get("status", "active") in {"active", "claimed", "running"}]
    return tuple(sorted((_stable_value(row) for row in active), key=lambda row: (_id_number(row.get("horizon_id", "H0")), row.get("agent_id", ""))))


def _timeline(events: Iterable[Any]) -> tuple[TimelineItem, ...]:
    rows = []
    for event in events:
        data = _to_dict(event)
        rows.append(
            TimelineItem(
                ts=str(data.get("ts", "")),
                horizon_id=str(data.get("horizon_id") or "global"),
                event_type=str(data.get("event_type", "")),
                severity=str(data.get("severity", "info")),
                message=str(data.get("message", "")),
            )
        )
    return tuple(rows[-50:])


def _default_sections(model: DashboardModel) -> tuple[DashboardSection, ...]:
    return (
        DashboardSection("overview", "Overview", summary=model.overview),
        DashboardSection("board", "Horizon Board", rows=model.board),
        DashboardSection("next", "Next Recommendations", rows=model.next_recommendations),
        DashboardSection("blocked", "Blocked Horizons", rows=model.blocked_horizons),
        DashboardSection("conflicts", "Conflict Summary", summary=model.conflict_summary),
        DashboardSection("locks", "Active Locks", rows=model.active_locks),
        DashboardSection("timeline", "Timeline", rows=tuple(item.to_dict() for item in model.timeline)),
    )


def _overview_html(overview: dict[str, Any]) -> str:
    cards = "".join(f'<article class="metric"><span>{escape(str(key).replace("_", " ").title())}</span><strong>{escape(str(value))}</strong></article>' for key, value in overview.items() if key != "status_counts")
    statuses = "".join(f"<li><span>{escape(key)}</span><strong>{value}</strong></li>" for key, value in overview.get("status_counts", {}).items())
    return f'<section id="overview" class="section"><h2>Overview</h2><div class="metrics">{cards}</div><ul class="status-list">{statuses}</ul></section>'


def _board_html(rows: Iterable[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("status", "unknown")), []).append(row)
    columns = []
    for status in sorted(grouped):
        cards = "".join(
            f'<article class="horizon-card"><strong>{escape(str(row["horizon_id"]))}</strong><span>{escape(str(row["title"]))}</span><small>wave {escape(str(row.get("wave", "")))} · diagnostics {escape(str(row.get("diagnostics", 0)))}</small></article>'
            for row in grouped[status]
        )
        columns.append(f'<div class="board-column"><h3>{escape(status.replace("_", " ").title())}</h3>{cards}</div>')
    return '<section id="board" class="section"><h2>Horizon Board</h2><div class="board">' + "".join(columns) + "</div></section>"


def _table_section(section_id: str, title: str, rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> str:
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(_cell(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    header = "".join(f"<th>{escape(column.replace('_', ' ').title())}</th>" for column in columns)
    empty = f'<p class="empty">No {escape(title.lower())}.</p>' if not body else ""
    table = f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>" if body else ""
    return f'<section id="{section_id}" class="section"><h2>{escape(title)}</h2>{empty}{table}</section>'


def _summary_section(section_id: str, title: str, summary: dict[str, Any]) -> str:
    rows = "".join(f"<li><span>{escape(str(key).replace('_', ' ').title())}</span><strong>{escape(str(value))}</strong></li>" for key, value in summary.items())
    return f'<section id="{section_id}" class="section"><h2>{escape(title)}</h2><ul class="summary">{rows}</ul></section>'


def _timeline_html(rows: Iterable[dict[str, Any]]) -> str:
    items = "".join(
        f'<li><time>{escape(str(row["ts"]))}</time><strong>{escape(str(row["horizon_id"]))}</strong><span>{escape(str(row["event_type"]))}</span><p>{escape(str(row["message"]))}</p></li>'
        for row in rows
    )
    return f'<section id="timeline" class="section"><h2>Timeline</h2><ol class="timeline">{items}</ol></section>'


def _css() -> str:
    return """
:root{color-scheme:light dark;--bg:#f7f7f5;--panel:#ffffff;--text:#222;--muted:#626866;--line:#d9ddd8;--accent:#226f54;--bad:#a33a2a}
[data-theme="dark"]{--bg:#161817;--panel:#202321;--text:#f1f3ef;--muted:#a8afaa;--line:#3a403c;--accent:#76c49a;--bad:#f08b7a}
@media (prefers-color-scheme: dark){[data-theme="auto"]{--bg:#161817;--panel:#202321;--text:#f1f3ef;--muted:#a8afaa;--line:#3a403c;--accent:#76c49a;--bad:#f08b7a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.dashboard{max-width:1280px;margin:0 auto;padding:24px}.topbar{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:16px}.eyebrow{margin:0;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}h1,h2,h3{margin:0}h1{font-size:28px}h2{font-size:18px;margin-bottom:12px}.section{padding:20px 0;border-bottom:1px solid var(--line)}button{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:8px 12px;border-radius:6px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.metric,.horizon-card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px}.metric span,.horizon-card small{display:block;color:var(--muted)}.metric strong{font-size:24px}.status-list,.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;padding:0;margin:12px 0 0;list-style:none}.status-list li,.summary li{display:flex;justify-content:space-between;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:8px 10px}.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.board-column{display:grid;gap:8px;align-content:start}.horizon-card{display:grid;gap:4px}table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line)}th,td{text-align:left;border-bottom:1px solid var(--line);padding:8px;vertical-align:top}th{color:var(--muted);font-size:12px;text-transform:uppercase}.empty{color:var(--muted)}.timeline{display:grid;gap:8px;padding:0;margin:0;list-style:none}.timeline li{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:10px}.timeline time,.timeline span{color:var(--muted);margin-right:8px}
""".strip()


def _js() -> str:
    return """
document.getElementById('theme-toggle').addEventListener('click',function(){var root=document.documentElement;var current=root.getAttribute('data-theme')||'auto';root.setAttribute('data-theme',current==='dark'?'light':'dark');});
""".strip()


def _cell(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _status(record: HorizonRecord | dict[str, Any]) -> str:
    value = _record_field(record, "status")
    if isinstance(value, HorizonStatus):
        return value.value
    return str(value or "unknown")


def _record_field(record: HorizonRecord | dict[str, Any], field_name: str) -> Any:
    if isinstance(record, dict):
        return record.get(field_name)
    return getattr(record, field_name)


def _diagnostics_for(doctor: Any, horizon_id: Any) -> list[dict[str, Any]]:
    if doctor is None:
        return []
    wanted = str(HorizonId(horizon_id))
    data = _to_dict(doctor)
    rows = data.get("diagnostics", ())
    return [row for row in rows if row.get("horizon_id") == wanted]


def _doctor_error_count(doctor: Any) -> int:
    if doctor is None:
        return 0
    return sum(1 for row in _to_dict(doctor).get("diagnostics", ()) if row.get("severity") == "error")


def _blocking_conflict_count(conflicts: Any) -> int:
    if conflicts is None:
        return 0
    data = _to_dict(conflicts)
    return int(data.get("blocking_pair_count", 0))


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return dict(value)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable_value(item) for item in value]
    return value


def _id_number(value: Any) -> int:
    try:
        return HorizonId(value).number
    except ValueError:
        return 0
