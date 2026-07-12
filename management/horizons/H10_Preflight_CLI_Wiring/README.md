# HM-H10 Preflight CLI Wiring

Owner: agent-toolchain
Source of Truth: management/horizons/H10_Preflight_CLI_Wiring/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 5).

## Purpose

Replace the preflight CLI stub with the real preflight implementation over selected corpus state.

## Goals

- Add preflight command arguments for horizon, agent, and mode.
- Return structured checks, blockers, and allowed paths.
- Use selected corpus state, locks, doctor report, conflicts, and changed paths.

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

- `management/subprojects/horizon-manager/src/horizon_manager/cli.py`
- `management/subprojects/horizon-manager/src/horizon_manager/preflight.py`
- `management/subprojects/horizon-manager/tests/test_horizon_cli.py`
- `management/subprojects/horizon-manager/tests/test_horizon_preflight.py`

## Concurrency

Wave 5. Needs: H06/H08/H09.
