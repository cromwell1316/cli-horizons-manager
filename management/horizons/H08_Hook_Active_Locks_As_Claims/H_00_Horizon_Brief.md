# H08 Horizon Brief

Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md

## Problem

Make Hook Check treat active locks for the current agent as effective claims.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for hook active locks as claims.

## Success Criteria

- Merge explicit --claim values with active lock-store claims.
- Preserve strict foreign owned-file blocking.
- Cover CLI and interactive hook flows with tests.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
