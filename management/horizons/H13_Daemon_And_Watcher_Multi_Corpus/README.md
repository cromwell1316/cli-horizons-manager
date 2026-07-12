# HM-H13 Daemon And Watcher Multi Corpus

Owner: agent-toolchain
Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 6).

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

- `src/horizon_manager/server.py`
- `src/horizon_manager/watch.py`
- `tests/test_horizon_server.py`
- `tests/test_horizon_watch.py`

## Concurrency

Wave 6. Needs: H02/H06.

## Completion Notes

- Daemon config and state expose selected corpus metadata, including corpus name, title, repo root, horizons dir, and generated dir.
- `/metadata` is available as a read-only daemon endpoint.
- Watcher configs can derive watched roots from registered corpora and build corpus-scoped refresh plans.
- Localhost-only daemon validation remains enforced.
