# HM-H04 Context Propagation Across Commands

Owner: agent-toolchain
Source of Truth: management/horizons/H04_Context_Propagation_Across_Commands/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 2).

## Purpose

Ensure every command runs against the selected corpus context instead of implicit HCO defaults.

## Goals

- Route repo root, horizons dir, generated dir, locks, and events through CommandContext.
- Include selected corpus in JSON/text output.
- Preserve explicit path overrides for scripts.

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
- `management/subprojects/horizon-manager/tests/test_horizon_cli.py`

## Concurrency

Wave 2. Needs: H02.
