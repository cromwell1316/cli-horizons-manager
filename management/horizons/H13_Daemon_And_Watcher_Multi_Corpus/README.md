# HM-H13 Daemon And Watcher Multi Corpus

Owner: agent-toolchain
Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md
Lifecycle: planned
Document Class: horizon

Status: planned (Wave 6).

## Purpose

Teach daemon and watcher contracts to operate over selected or registered corpora.

## Goals

- Add corpus metadata to daemon state and refresh endpoints.
- Watch registered corpus roots with corpus-scoped refresh plans.
- Keep localhost-only daemon safety.

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

- `management/subprojects/horizon-manager/src/horizon_manager/server.py`
- `management/subprojects/horizon-manager/src/horizon_manager/watch.py`
- `management/subprojects/horizon-manager/tests/test_horizon_server.py`
- `management/subprojects/horizon-manager/tests/test_horizon_watch.py`

## Concurrency

Wave 6. Needs: H02/H06.
