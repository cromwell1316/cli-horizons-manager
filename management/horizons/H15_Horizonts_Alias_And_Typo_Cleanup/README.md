# HM-H15 Horizonts Alias And Typo Cleanup

Owner: agent-toolchain
Source of Truth: management/horizons/H15_Horizonts_Alias_And_Typo_Cleanup/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 7).

## Purpose

Resolve the accidental horizonts spelling support by formalizing or removing it.

## Goals

- Decide whether horizonts is an official alias.
- Update hook/watch tests and README to match the decision.
- Remove stale typo directories if not official.

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

- `src/horizon_manager/hooks.py`
- `src/horizon_manager/watch.py`
- `tests/test_horizon_hooks.py`
- `tests/test_horizon_watch.py`
- `README.md`

## Concurrency

Wave 7. Needs: H07/H09.

## Completion Notes

- `horizons` is the canonical directory name.
- `horizonts` is formalized as a deprecated compatibility alias for hook and watcher path classification only.
- No stale `horizonts` directories exist in this checkout.
