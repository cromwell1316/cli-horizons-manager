# HM-H04 Context Propagation Across Commands

Owner: agent-toolchain
Source of Truth: management/horizons/H04_Context_Propagation_Across_Commands/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 2).

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

- `src/horizon_manager/cli.py`
- `tests/test_horizon_cli.py`

## Concurrency

Wave 2. Needs: H02.

## Completion Notes

- `CommandContext` now normalizes the selected corpus and records explicit repo root,
  horizons dir, and generated dir overrides.
- Every `run_command` result receives `data.context` with corpus, repo root, horizons
  dir, generated dir, and override flags.
- Text output prints the selected corpus and horizons dir when context metadata is
  present.
- Locks and events continue to use `CommandContext.path(...)`, preserving generated-dir
  overrides for scripts.
