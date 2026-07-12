# HM-H06 Corpus Scoped Generated Outputs

Owner: agent-toolchain
Source of Truth: management/horizons/H06_Corpus_Scoped_Generated_Outputs/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 3).

## Purpose

Make every generated output land beside the selected corpus instead of HCO-only defaults.

## Goals

- Route state, doctor, conflicts, locks, events, dashboard, DAG, and history outputs through corpus context.
- Remove runtime dependence on HCO module DEFAULT_OUTPUT paths.
- Keep standalone module CLIs compatible through explicit output arguments.

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

- `src/horizon_manager/parser.py`
- `src/horizon_manager/conflicts.py`
- `src/horizon_manager/locks.py`
- `src/horizon_manager/render.py`
- `src/horizon_manager/dag_render.py`
- `src/horizon_manager/history.py`
- `tests/test_horizon_model.py`
- `tests/test_horizon_conflicts.py`
- `tests/test_horizon_locks.py`
- `tests/test_horizon_render.py`
- `tests/test_horizon_dag_render.py`
- `tests/test_horizon_history.py`

## Concurrency

Wave 3. Needs: H04.

## Completion Notes

- Standalone module defaults now target this repository's `management/` directory and
  `management/horizons` corpus.
- HCO paths remain supported through explicit `--horizons-dir` and `--output`
  arguments where module CLIs expose them.
- Regression tests assert parser, conflicts, locks, dashboard, DAG, and history defaults
  do not point at `hermes-consistency-orchestrator`.
