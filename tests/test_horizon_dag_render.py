"""Verification tests for H49 DAG renderer."""

from __future__ import annotations

from pathlib import Path
import tempfile

from horizon_manager.dag_render import DEFAULT_OUTPUT, build_dag_model, render_dag_html, write_dag
from horizon_manager.model import (
    HorizonDependency,
    HorizonId,
    HorizonRecord,
    HorizonState,
    HorizonStatus,
    OwnedPath,
    OwnedPathMode,
)


def test_dag_default_output_is_standalone_management_path() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assert DEFAULT_OUTPUT == project_root / "management/horizon_dependency_graph.html"
    assert "hermes-consistency-orchestrator" not in DEFAULT_OUTPUT.as_posix()


def test_dag_model_uses_state_nodes_and_dependency_edges() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, 7, "state.py"),
        _record("H48", "Dashboard", HorizonStatus.IMPLEMENTED, 10, "render.py", deps=("H39",)),
        _record("H49", "DAG", HorizonStatus.PLANNED, 10, "dag.py", deps=("H39", "H48")),
    )

    model = build_dag_model(state)

    assert [str(node.id) for node in model.nodes] == ["H39", "H48", "H49"]
    assert [(str(edge.source), str(edge.target)) for edge in model.edges] == [
        ("H48", "H39"),
        ("H49", "H39"),
        ("H49", "H48"),
    ]
    assert model.metadata["horizon_count"] == 3
    assert model.metadata["edge_count"] == 3


def test_cross_wave_and_start_now_are_derived() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, 7, "state.py"),
        _record("H49", "DAG", HorizonStatus.PLANNED, 10, "dag.py", deps=("H39",)),
    )

    model = build_dag_model(state)
    h49 = [node for node in model.nodes if node.id == HorizonId("H49")][0]

    assert h49.start_now is True
    assert model.edges[0].cross_wave is True


def test_active_lock_suppresses_start_now_badge() -> None:
    state = _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, 7, "state.py"),
        _record("H49", "DAG", HorizonStatus.PLANNED, 10, "dag.py", deps=("H39",)),
    )

    model = build_dag_model(state, locks={"locks": [{"horizon_id": "H49", "status": "active"}]})
    h49 = [node for node in model.nodes if node.id == HorizonId("H49")][0]

    assert h49.start_now is False


def test_rendered_html_has_dynamic_svg_routing_and_theme_tokens() -> None:
    html = render_dag_html(build_dag_model(_fixture_state()))

    assert "getBoundingClientRect()" in html
    assert "ResizeObserver" in html
    assert "MutationObserver" in html
    assert "<svg class=\"edges\"" in html
    assert "marker-end" in html
    assert "--accent: #4A7850" in html
    assert "prefers-color-scheme: dark" in html
    assert ':root[data-theme="dark"]' in html


def test_rendered_html_uses_corpus_title_when_provided() -> None:
    html = render_dag_html(build_dag_model(_fixture_state()), title="Demo Corpus Dependency DAG")

    assert "<title>Demo Corpus Dependency DAG</title>" in html
    assert "<h1>Demo Corpus Dependency DAG</h1>" in html


def test_rendered_html_preserves_scroll_contract_and_cross_wave_style() -> None:
    html = render_dag_html(build_dag_model(_fixture_state()))

    assert "body {\n  margin: 0;\n  overflow-x: hidden;" in html
    assert ".graph-scroll {\n  overflow-x: auto;" in html
    assert "cross-wave" in html
    assert "stroke-dasharray" in html
    assert "grid-template-columns" in html


def test_render_output_is_deterministic() -> None:
    model = build_dag_model(_fixture_state())

    assert render_dag_html(model) == render_dag_html(model)


def test_write_dag_writes_self_contained_artifact() -> None:
    html = render_dag_html(build_dag_model(_fixture_state()))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "horizon_dependency_graph.html"
        write_dag(path, html)
        written = path.read_text(encoding="utf-8")

    assert written == html
    assert "https://" not in written
    assert "fonts.googleapis" not in written


def _fixture_state() -> HorizonState:
    return _state(
        _record("H39", "State", HorizonStatus.IMPLEMENTED, 7, "state.py"),
        _record("H48", "Dashboard", HorizonStatus.IMPLEMENTED, 10, "render.py", deps=("H39",)),
        _record("H49", "DAG", HorizonStatus.PLANNED, 10, "dag.py", deps=("H39", "H48")),
    )


def _record(
    horizon_id: str,
    title: str,
    status: HorizonStatus,
    wave: int,
    path: str,
    *,
    deps: tuple[str, ...] = (),
) -> HorizonRecord:
    return HorizonRecord(
        id=HorizonId(horizon_id),
        title=title,
        directory=f"horizons/{horizon_id}",
        source_path=f"horizons/{horizon_id}/README.md",
        status=status,
        wave=wave,
        dependencies=tuple(HorizonDependency(HorizonId(dep), "test") for dep in deps),
        owned_files=(OwnedPath(path, OwnedPathMode.EXCLUSIVE),),
    )


def _state(*records: HorizonRecord) -> HorizonState:
    return HorizonState(tuple(records), generated_from="test")


if __name__ == "__main__":
    test_dag_model_uses_state_nodes_and_dependency_edges()
    test_cross_wave_and_start_now_are_derived()
    test_active_lock_suppresses_start_now_badge()
    test_rendered_html_has_dynamic_svg_routing_and_theme_tokens()
    test_rendered_html_preserves_scroll_contract_and_cross_wave_style()
    test_render_output_is_deterministic()
    test_write_dag_writes_self_contained_artifact()
