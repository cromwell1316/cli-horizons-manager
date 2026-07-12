# HM-H02 Config Backed Corpus Registry

Owner: agent-toolchain
Source of Truth: management/horizons/H02_Config_Backed_Corpus_Registry/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 1).

## Purpose

Replace hardcoded project assumptions with a registry that can describe every managed horizon corpus.

## Goals

- Load built-in corpora and future configured corpora through one API.
- Represent repo root, horizons dir, generated dir, name, and title.
- Validate missing or empty corpus paths deterministically.

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

- `src/horizon_manager/corpus.py`
- `tests/test_horizon_corpus.py`

## Concurrency

Wave 1. Needs: H01.

## Completion Notes

- Built-in corpora and optional TOML-configured corpora load through one registry API.
- `HORIZON_MANAGER_CORPORA_CONFIG` can point at a future corpus config file without
  changing CLI call sites.
- Corpus path diagnostics are deterministic and cover missing paths, non-directories,
  and empty horizon directories.
