# HM-H01 External App Boundary And Packaging

Owner: agent-toolchain
Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 1).

## Purpose

Make Horizon Manager explicitly external to any one managed project, with package metadata and operator documentation that do not imply HCO ownership.

## Goals

- Define the external application boundary in README and package metadata.
- Keep project-specific runtime paths behind corpus selection.
- Document install and WSL usage for an external operator tool.

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

- `pyproject.toml`
- `README.md`
- `src/horizon_manager/__init__.py`
- `src/horizon_manager/parser.py`
- `tests/test_horizon_model.py`

## Concurrency

Wave 1. No upstream horizon dependency.

## Completion Notes

- Package distribution is named `cli-horizons-manager`.
- Console entry point remains `horizon-manager`.
- README defines the external application boundary, WSL install flow, selected-corpus
  runtime path rule, and self-management corpus.
- Parser source paths are normalized relative to the current standalone checkout when
  managed horizons live inside this repository.
