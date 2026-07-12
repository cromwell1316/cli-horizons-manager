# HM-H05 Interactive Corpus Selector

Owner: agent-toolchain
Source of Truth: management/horizons/H05_Interactive_Corpus_Selector/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 2).

## Purpose

Make the keyboard-first console safe for multi-corpus operation.

## Goals

- Show active corpus in the menu header.
- Add an in-session corpus selector.
- Render help without terminating the interactive loop.

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

- `src/horizon_manager/interactive.py`
- `tests/test_horizon_interactive.py`

## Concurrency

Wave 2. Needs: H03/H04.

## Completion Notes

- The main interactive menu shows active corpus and horizons directory in the header.
- Menu item `[0] Corpora` opens an in-session selector and switches `CommandContext`.
- Help is rendered with `build_parser().format_help()` and returns to the interactive
  loop instead of terminating through argparse `SystemExit`.
