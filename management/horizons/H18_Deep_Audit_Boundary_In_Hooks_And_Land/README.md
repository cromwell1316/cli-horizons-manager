# HM-H18 Deep Audit Boundary In Hooks And Land

Owner: agent-toolchain
Source of Truth: management/horizons/H18_Deep_Audit_Boundary_In_Hooks_And_Land/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 7).

## Purpose

Make detector-output boundaries explicit in hook and land behavior.

## Goals

- Keep hook diagnostics deterministic for detector output.
- Document allowed handling for deep-audit artifacts.
- Ensure land rejects detector outputs unless a corpus policy allows them.

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

- `management/subprojects/horizon-manager/src/horizon_manager/hooks.py`
- `management/subprojects/horizon-manager/src/horizon_manager/land.py`
- `management/subprojects/horizon-manager/tests/test_horizon_hooks.py`
- `management/subprojects/horizon-manager/tests/test_horizon_land.py`

## Concurrency

Wave 7. Needs: H09/H12.
