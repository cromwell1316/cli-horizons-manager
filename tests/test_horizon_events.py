"""Tests for the H44 Horizon Event Log."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.events import (  # noqa: E402
    EventSeverity,
    EventType,
    HorizonEvent,
    append_event,
    read_events,
    summarize_events,
)


def test_event_serialization_is_deterministic() -> None:
    event = _event("e2", "H44", EventType.PUSH, detail={"z": 2, "a": {"b": 1}})
    assert event.to_dict() == {
        "actor": "agent-toolchain",
        "correlation_id": "c1",
        "detail": {"a": {"b": 1}, "z": 2},
        "event_id": "e2",
        "event_type": "push",
        "horizon_id": "H44",
        "message": "push event",
        "schema_version": 1,
        "severity": "info",
        "source": "test",
        "ts": "2026-07-11T00:00:02Z",
    }
    assert event.to_json_line() == json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def test_append_writes_exactly_one_line_per_event() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        append_event(path, _event("e1", "H44", EventType.CLAIM), fsync=True)
        append_event(path, _event("e2", "H44", EventType.RELEASE))
        lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "claim"
    assert json.loads(lines[1])["event_type"] == "release"


def test_reader_filters_by_horizon_and_event_type() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        append_event(path, _event("e1", "H44", EventType.CLAIM))
        append_event(path, _event("e2", "H42", EventType.CLAIM))
        append_event(path, _event("e3", "H44", EventType.PUSH))
        assert [event.event_id for event in read_events(path, horizon_id="h44")] == ["e1", "e3"]
        assert [event.event_id for event in read_events(path, event_type="claim")] == ["e1", "e2"]
        assert [event.event_id for event in read_events(path, horizon_id="H44", event_type=EventType.PUSH)] == ["e3"]


def test_invalid_events_fail_before_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        for kwargs in (
            {"event_id": ""},
            {"actor": ""},
            {"message": ""},
            {"event_type": "invalid"},
            {"severity": "bad"},
            {"detail": {"bad": object()}},
        ):
            try:
                event = _event("e1", "H44", EventType.NOTE, **kwargs)
                append_event(path, event)
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError(f"invalid event accepted: {kwargs!r}")
        assert not path.exists()


def test_reader_rejects_invalid_jsonl() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "events.jsonl"
        path.write_text("{not-json}\n", encoding="utf-8")
        try:
            list(read_events(path))
        except ValueError as exc:
            assert "invalid event" in str(exc)
        else:
            raise AssertionError("invalid JSONL was accepted")


def test_summary_helpers_are_dashboard_ready() -> None:
    events = (
        _event("e1", "H44", EventType.CLAIM, ts="2026-07-11T00:00:01Z"),
        _event("e2", "H44", EventType.PREFLIGHT, ts="2026-07-11T00:00:02Z", severity=EventSeverity.WARN),
        _event("e3", "H42", EventType.RELEASE, ts="2026-07-11T00:00:03Z"),
        _event("e4", "H44", EventType.PUSH, ts="2026-07-11T00:00:04Z"),
    )
    summary = summarize_events(events).to_dict()
    assert summary["total"] == 4
    assert summary["by_type"] == {"claim": 1, "preflight": 1, "push": 1, "release": 1}
    assert summary["by_horizon"] == {"H42": 1, "H44": 3}
    assert summary["by_severity"] == {"info": 3, "warn": 1, "error": 0}
    assert summary["last_event_by_horizon"]["H44"]["event_type"] == "push"


def _event(
    event_id: str,
    horizon_id: str,
    event_type: EventType | str,
    *,
    ts: str | None = None,
    severity: EventSeverity | str = EventSeverity.INFO,
    detail: dict[str, object] | None = None,
    **overrides: object,
) -> HorizonEvent:
    values = {
        "event_id": event_id,
        "ts": ts or "2026-07-11T00:00:02Z",
        "actor": "agent-toolchain",
        "horizon_id": horizon_id,
        "event_type": event_type,
        "severity": severity,
        "message": f"{EventType.normalize(event_type).value} event",
        "correlation_id": "c1",
        "source": "test",
        "detail": detail or {},
    }
    values.update(overrides)
    return HorizonEvent(**values)


if __name__ == "__main__":
    test_event_serialization_is_deterministic()
    test_append_writes_exactly_one_line_per_event()
    test_reader_filters_by_horizon_and_event_type()
    test_invalid_events_fail_before_write()
    test_reader_rejects_invalid_jsonl()
    test_summary_helpers_are_dashboard_ready()
