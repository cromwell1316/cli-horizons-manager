# HM-H16 End To End Multi Corpus Acceptance

Owner: agent-toolchain
Source of Truth: management/horizons/H16_End_To_End_Multi_Corpus_Acceptance/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 8).

## Purpose

Prove the app works end-to-end across all configured corpora.

## Goals

- Validate state, doctor, conflicts, next, claim/release, hook, preflight, render, and land paths per corpus.
- Record command evidence for every registered corpus.
- Ensure outputs identify selected corpus.

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

- `management/subprojects/horizon-manager/tests/test_horizon_cli.py`
- `management/subprojects/horizon-manager/tests/test_horizon_server.py`
- `management/subprojects/horizon-manager/tests/test_horizon_interactive.py`
- `management/subprojects/horizon-manager/management/horizons/H16_End_To_End_Multi_Corpus_Acceptance/`

## Concurrency

Wave 8. Needs: H05/H10/H11/H12/H13.
