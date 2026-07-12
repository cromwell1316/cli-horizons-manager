"""Tests for the H39 canonical horizon state model and parser."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
PACKAGE_SRC = ROOT / "management/subprojects/horizon-manager/src"
sys.path.insert(0, str(PACKAGE_SRC))

from horizon_manager.model import HorizonId, HorizonState, HorizonStatus, OwnedPathMode  # noqa: E402
from horizon_manager.parser import DEFAULT_HORIZONS_DIR, DEFAULT_OUTPUT, parse_horizon_tree, parse_readme  # noqa: E402


def test_horizon_id_and_status_normalization() -> None:
    assert HorizonId("h39") == "H39"
    assert HorizonId("HCO-H7") == "H07"
    assert HorizonId(41).number == 41
    assert HorizonStatus.normalize("implemented (Wave 6, 2026-07-10)") is HorizonStatus.IMPLEMENTED
    assert HorizonStatus.normalize("in progress") is HorizonStatus.IN_PROGRESS
    assert HorizonStatus.normalize("") is HorizonStatus.UNKNOWN


def test_parser_defaults_are_standalone_management_paths() -> None:
    assert DEFAULT_HORIZONS_DIR == PACKAGE_SRC.parent / "management/horizons"
    assert DEFAULT_OUTPUT == PACKAGE_SRC.parent / "management/horizon_state.json"
    assert "hermes-consistency-orchestrator" not in DEFAULT_OUTPUT.as_posix()


def test_model_serialization_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "horizons"
        _write(
            root / "H02_Beta" / "README.md",
            """# HCO-H02 Beta

Status: planned (Wave 2, after H01).

## Owned Files (EXCLUSIVE)
- `src/beta.py`

## Concurrency
Wave 2, after H01.
""",
        )
        _write(
            root / "H01_Alpha" / "README.md",
            """# HCO-H01 Alpha

Status: implemented (Wave 1, 2026-07-01).

## Owned Files (EXCLUSIVE)
- `src/alpha.py`

## Concurrency
Wave 1 foundation.
""",
        )

        state = parse_horizon_tree(root)
        first = state.to_json()
        second = HorizonState(tuple(reversed(state.records)), generated_from=state.generated_from).to_json()
        assert first == second
        data = json.loads(first)
        assert [record["id"] for record in data["horizons"]] == ["H01", "H02"]
        assert data["dependency_edges"] == [{"from": "H01", "source": "after", "to": "H02"}]


def test_parser_extracts_modern_readme_fields() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "horizons"
        readme = root / "H39_Horizon_State_Model" / "README.md"
        _write(
            readme,
            """# HCO-H39 Horizon State Model

Status: planned (Wave 7, after H30/H31).

## Owned Files (EXCLUSIVE)
- `management/subprojects/horizon-manager/src/horizon_manager/model.py`
- planned generated output management/subprojects/hermes-consistency-orchestrator/horizon_state.json

## Consumed Contracts (READ-ONLY)
- `management/subprojects/hermes-consistency-orchestrator/horizons/**/README.md`

## Concurrency
Wave 7 foundation. After H30/H31. Blocks H40-H54.
""",
        )
        record = parse_readme(readme, root)
        assert record.id == "H39"
        assert record.title == "Horizon State Model"
        assert record.status is HorizonStatus.PLANNED
        assert record.wave == 7
        assert sorted({str(dep.id) for dep in record.dependencies}) == ["H30", "H31"]
        modes = {owned.path: owned.mode for owned in record.owned_files}
        assert modes["management/subprojects/horizon-manager/src/horizon_manager/model.py"] is OwnedPathMode.EXCLUSIVE
        assert modes["management/subprojects/hermes-consistency-orchestrator/horizon_state.json"] is OwnedPathMode.GENERATED
        assert modes["management/subprojects/hermes-consistency-orchestrator/horizons/**/README.md"] is OwnedPathMode.READ_ONLY


def test_parser_warns_on_missing_optional_sections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "horizons"
        readme = root / "H05_No_Metadata" / "README.md"
        _write(readme, "# HCO-H05 No Metadata\n")
        record = parse_readme(readme, root)
        codes = {warning.code for warning in record.warnings}
        assert {"missing_status", "missing_wave", "missing_concurrency", "missing_owned_files"} <= codes
        assert record.status is HorizonStatus.UNKNOWN


def test_parser_uses_current_checkout_for_nested_standalone_paths(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        checkout = Path(tmp) / "horizon-manager"
        root = checkout / "management/horizons"
        readme = root / "H01_External_App_Boundary" / "README.md"
        _write(
            readme,
            """# HM-H01 External App Boundary

Status: implemented (Wave 1).

## Owned Files (EXCLUSIVE)
- `README.md`

## Concurrency
Wave 1.
""",
        )
        monkeypatch.chdir(checkout)

        record = parse_readme(readme, root)

        assert record.directory == "management/horizons/H01_External_App_Boundary"
        assert record.source_path == "management/horizons/H01_External_App_Boundary/README.md"


def test_real_horizon_tree_parses_current_corpus() -> None:
    state = parse_horizon_tree(ROOT / "management/subprojects/hermes-consistency-orchestrator/horizons")
    assert len(state.records) >= 54
    assert state.require("H01").status is HorizonStatus.IMPLEMENTED
    assert state.require("H39").wave == 7
    assert any(edge["from"] == "H39" and edge["to"] == "H40" for edge in state.dependency_edges())
    assert "management/subprojects/horizon-manager/src/horizon_manager/model.py" in state.owned_path_index()
    assert json.loads(state.to_json())["horizon_count"] == len(state.records)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    test_horizon_id_and_status_normalization()
    test_model_serialization_is_deterministic()
    test_parser_extracts_modern_readme_fields()
    test_parser_warns_on_missing_optional_sections()
    test_real_horizon_tree_parses_current_corpus()
