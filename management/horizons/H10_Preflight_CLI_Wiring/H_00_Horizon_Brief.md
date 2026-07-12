# H10 Horizon Brief

Source of Truth: management/horizons/H10_Preflight_CLI_Wiring/README.md

## Problem

Replace the preflight CLI stub with the real preflight implementation over selected corpus state.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for preflight cli wiring.

## Success Criteria

- Add preflight command arguments for horizon, agent, and mode.
- Return structured checks, blockers, and allowed paths.
- Use selected corpus state, locks, doctor report, conflicts, and changed paths.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
