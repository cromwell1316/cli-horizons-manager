# HM-H19 Product UX Status And Operator Feedback

Owner: agent-toolchain
Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 8).

## Purpose

Improve operator feedback so corpus state and next actions are visible without reading raw JSON.

## Goals

- Show active corpus, horizon counts, lock counts, and dirty status.
- Render concise doctor/hook/preflight summaries.
- Keep keyboard-first interaction script-friendly.

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

- `management/subprojects/horizon-manager/src/horizon_manager/interactive.py`
- `management/subprojects/horizon-manager/src/horizon_manager/render.py`
- `management/subprojects/horizon-manager/tests/test_horizon_interactive.py`
- `management/subprojects/horizon-manager/tests/test_horizon_render.py`

## Concurrency

Wave 8. Needs: H05/H11.
