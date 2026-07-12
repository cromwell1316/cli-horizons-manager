# HM-H08 Hook Active Locks As Claims

Owner: agent-toolchain
Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 4).

## Purpose

Make Hook Check treat active locks for the current agent as effective claims.

## Goals

- Merge explicit --claim values with active lock-store claims.
- Preserve strict foreign owned-file blocking.
- Cover CLI and interactive hook flows with tests.

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
- `management/subprojects/horizon-manager/src/horizon_manager/cli.py`
- `management/subprojects/horizon-manager/tests/test_horizon_hooks.py`

## Concurrency

Wave 4. Needs: H04/H06.
