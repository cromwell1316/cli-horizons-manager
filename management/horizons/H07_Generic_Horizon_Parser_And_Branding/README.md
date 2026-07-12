# HM-H07 Generic Horizon Parser And Branding

Owner: agent-toolchain
Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 3).

## Purpose

Remove HCO branding assumptions from generic parsing and rendering while keeping HCO documents compatible.

## Goals

- Accept generic Hxx documents as first-class input.
- Keep HCO-Hxx title normalization backward compatible.
- Make empty corpus diagnostics clear.

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

- `management/subprojects/horizon-manager/src/horizon_manager/parser.py`
- `management/subprojects/horizon-manager/src/horizon_manager/model.py`
- `management/subprojects/horizon-manager/tests/test_horizon_model.py`

## Concurrency

Wave 3. Needs: H01/H02.
