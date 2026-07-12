# HM-H03 Corpus Registry CLI Commands

Owner: agent-toolchain
Source of Truth: management/horizons/H03_Corpus_Registry_CLI_Commands/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 2).

## Purpose

Expose corpus registry inspection and management through the CLI.

## Goals

- Add corpus list/doctor surfaces.
- Show horizon counts and path health for every corpus.
- Keep mutation commands explicit and reversible.

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

- `horizon-manager corpora` remains a backward-compatible alias for `corpora list`.
- `horizon-manager corpora list` emits all registry rows with horizon counts and path
  health.
- `horizon-manager corpora doctor` fails deterministically when registry paths are
  missing, non-directories, or empty horizon directories.
- H03 introduces no registry mutation command; the CLI surface is read-only, so future
  mutation commands must be explicit and independently reversible.
