# HM-H11 Render Dashboard DAG History CLI Wiring

Owner: agent-toolchain
Source of Truth: management/horizons/H11_Render_Dashboard_DAG_History_CLI_Wiring/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 5).

## Purpose

Replace the render CLI stub with real dashboard, DAG, and history render commands scoped to the selected corpus.

## Goals

- Add target flags and output controls.
- Use corpus title and generated dir in artifacts.
- Keep render output deterministic.

## Files

- H_00_Horizon_Brief.md
- H_01_Baseline.md
- H_02_Target_Model.md
- H_03_Workstreams.md
- H_04_Governance_And_Safety_Boundaries.md
- V_00_Validation_Plan.md
- V_01_Risk_Register.md
- V_02_Acceptance_Matrix.md
- V_03_Implementation_Evidence.md

## Owned Files (EXCLUSIVE)

- `src/horizon_manager/cli.py`
- `src/horizon_manager/render.py`
- `src/horizon_manager/dag_render.py`
- `src/horizon_manager/history.py`
- `tests/test_horizon_render.py`
- `tests/test_horizon_dag_render.py`
- `tests/test_horizon_history.py`

## Owned Files (SHARED)

- `tests/test_horizon_cli.py`

## Concurrency

Wave 5. Needs: H06.

## Completion Notes

- `render` now supports dashboard, DAG, history, and all-target rendering.
- Dashboard and DAG artifacts use the selected corpus title and selected generated directory.
- History snapshots are written below the selected generated directory by default and include corpus metadata.
