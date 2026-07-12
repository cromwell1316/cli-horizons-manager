# H12 Horizon Brief

Source of Truth: management/horizons/H12_Land_Gate_CLI_Wiring/README.md

## Problem

Replace the land CLI stub with the real safe-land gate.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for land gate cli wiring.

## Success Criteria

- Add dry-run, commit-only, and commit-and-push modes.
- Stage only preflight-allowed files.
- Record events in the selected corpus event log.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
