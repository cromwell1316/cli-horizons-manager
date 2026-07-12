"""Tests for the H48 dashboard renderer."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.conflicts import Conflict, ConflictKind, ConflictMatrix, ConflictSeverity  # noqa: E402
from horizon_manager.doctor import Diagnostic, DoctorReport, Severity  # noqa: E402
from horizon_manager.events import EventType, HorizonEvent  # noqa: E402
from horizon_manager.locks import HorizonLock, LockSnapshot, LockStatus  # noqa: E402
from horizon_manager.model import HorizonDependency, HorizonRecord, HorizonState, HorizonStatus, OwnedPath, OwnedPathMode  # noqa: E402
from horizon_manager.next import RecommendationReport  # noqa: E402
from horizon_manager.render import DEFAULT_OUTPUT, build_dashboard_model, render_dashboard, write_dashboard  # noqa: E402


def test_render_default_output_is_standalone_management_path() -> None:
    assert DEFAULT_OUTPUT == PACKAGE_SRC.parent / "management/horizon_dashboard.html"
    assert "hermes-consistency-orchestrator" not in DEFAULT_OUTPUT.as_posix()


def test_dashboard_model_and_render_are_deterministic() -> None:
    model = _model()
    assert model.to_dict() == build_dashboard_model(*_inputs()).to_dict()
    html = render_dashboard(model)
    assert html == render_dashboard(_model())
    assert html.startswith("<!doctype html>")
    assert 'id="dashboard"' in html


def test_required_sections_render() -> None:
    html = render_dashboard(_model(), theme="light")
    for section_id in ("overview", "board", "next", "blocked", "conflicts", "locks", "timeline"):
        assert f'id="{section_id}"' in html
    assert "Horizon Board" in html
    assert "Next Recommendations" in html
    assert "Blocked Horizons" in html


def test_no_external_assets_are_referenced() -> None:
    html = render_dashboard(_model())
    forbidden = ("https://", "http://", "<link", "<img", "@import", "src=")
    for token in forbidden:
        assert token not in html


def test_theme_tokens_support_auto_light_dark() -> None:
    for theme in ("auto", "light", "dark"):
        html = render_dashboard(_model(), theme=theme)
        assert f'data-theme="{theme}"' in html
        assert "--bg:" in html
        assert "prefers-color-scheme" in html
    try:
        render_dashboard(_model(), theme="sepia")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid theme accepted")


def test_write_dashboard_writes_html() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "horizon_dashboard.html"
        html = render_dashboard(_model(), theme="dark")
        write_dashboard(path, html)
        assert path.read_text(encoding="utf-8") == html


def _model():
    return build_dashboard_model(*_inputs())


def _inputs():
    state = HorizonState(
        (
            HorizonRecord(
                id="H39",
                title="State Model",
                directory="h/H39",
                source_path="h/H39/README.md",
                status=HorizonStatus.IMPLEMENTED,
                wave=7,
                concurrency="Wave 7.",
                owned_files=(OwnedPath("state.py", OwnedPathMode.EXCLUSIVE, "", "owned"),),
            ),
            HorizonRecord(
                id="H48",
                title="Dashboard Renderer",
                directory="h/H48",
                source_path="h/H48/README.md",
                status=HorizonStatus.PLANNED,
                wave=10,
                concurrency="Wave 10.",
                dependencies=(HorizonDependency("H39", "after", "after H39"),),
                owned_files=(OwnedPath("render.py", OwnedPathMode.EXCLUSIVE, "", "owned"),),
            ),
        )
    )
    doctor = DoctorReport(
        diagnostics=(
            Diagnostic(
                code="missing_owned_files",
                severity=Severity.ERROR,
                horizon_id="H48",
                message="blocked for test",
                source_path="h/H48/README.md",
                section="Owned Files",
            ),
        ),
        horizon_count=2,
        edge_count=1,
    )
    conflicts = ConflictMatrix(
        (
            Conflict(
                "H39",
                "H48",
                ConflictKind.DEPENDENCY_ORDER,
                ConflictSeverity.INFO,
                explanation="ordered",
            ),
        )
    )
    locks = LockSnapshot(
        locks=(
            HorizonLock("H48", "agent-a", LockStatus.ACTIVE, claimed_at="2026-07-11T00:00:00Z", expires_at="2026-07-11T02:00:00Z"),
        )
    )
    next_report = RecommendationReport(recommendations=(), generated_at="2026-07-11T00:00:00Z")
    events = (
        HorizonEvent(
            event_id="e1",
            ts="2026-07-11T00:00:00Z",
            actor="agent-a",
            horizon_id="H48",
            event_type=EventType.NOTE,
            message="dashboard event",
        ),
    )
    return state, doctor, conflicts, locks, next_report, events


if __name__ == "__main__":
    test_dashboard_model_and_render_are_deterministic()
    test_required_sections_render()
    test_no_external_assets_are_referenced()
    test_theme_tokens_support_auto_light_dark()
    test_write_dashboard_writes_html()
