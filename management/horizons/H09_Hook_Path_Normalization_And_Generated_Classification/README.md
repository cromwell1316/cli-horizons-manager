# HM-H09 Hook Path Normalization And Generated Classification

Owner: agent-toolchain
Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 4).

## Purpose

Make hook classification correct for every corpus and for generated outputs.

## Goals

- Normalize changed paths against the selected repo root.
- Classify horizon_*.json/jsonl/html relative to selected generated dir.
- Remove HCO-only generated path checks from runtime behavior.

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
- `tests/test_horizon_hooks.py`

## Owned Files (SHARED)

- `src/horizon_manager/cli.py`

## Concurrency

Wave 4. Needs: H04/H06.

## Completion Notes

- Hook changed paths are normalized to repo-relative POSIX paths before classification and state ownership checks.
- Generated hook outputs are classified only when `horizon_*.json`, `horizon_*.jsonl`, or `horizon_*.html` lives directly under the selected generated directory.
- Runtime generated-output classification no longer depends on a hard-coded HCO path.
