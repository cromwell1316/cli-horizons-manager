# HM-H12 Land Gate CLI Wiring

Owner: agent-toolchain
Source of Truth: management/horizons/H12_Land_Gate_CLI_Wiring/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 6).

## Purpose

Replace the land CLI stub with the real safe-land gate.

## Goals

- Add dry-run, commit-only, and commit-and-push modes.
- Stage only preflight-allowed files.
- Record events in the selected corpus event log.

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
- `management/subprojects/horizon-manager/src/horizon_manager/land.py`
- `management/subprojects/horizon-manager/tests/test_horizon_land.py`
- `management/subprojects/horizon-manager/tests/test_horizon_cli.py`

## Concurrency

Wave 6. Needs: H10.
