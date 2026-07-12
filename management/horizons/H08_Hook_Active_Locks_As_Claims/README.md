# HM-H08 Hook Active Locks As Claims

Owner: agent-toolchain
Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 4).

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

- `src/horizon_manager/hooks.py`
- `tests/test_horizon_hooks.py`
- `tests/test_horizon_interactive.py`

## Completion Notes

- Hook checks now merge explicit `--claim` values with active, unexpired lock-store claims owned by the same `agent_id`.
- Foreign active locks do not count as claims for the current agent and still block owned-file edits.
- CLI hook flow uses `horizon_locks.json` automatically, and interactive Hook Check delegates to that CLI path without requiring manual claim arguments.

## Concurrency

Wave 4. Needs: H04/H06.
