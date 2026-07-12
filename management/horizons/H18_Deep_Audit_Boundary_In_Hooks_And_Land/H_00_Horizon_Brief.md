# H18 Horizon Brief

Source of Truth: management/horizons/H18_Deep_Audit_Boundary_In_Hooks_And_Land/README.md

## Problem

Make detector-output boundaries explicit in hook and land behavior.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for deep audit boundary in hooks and land.

## Success Criteria

- Keep hook diagnostics deterministic for detector output.
- Document allowed handling for deep-audit artifacts.
- Ensure land rejects detector outputs unless a corpus policy allows them.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
