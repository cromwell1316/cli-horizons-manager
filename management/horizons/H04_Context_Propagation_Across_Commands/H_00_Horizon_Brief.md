# H04 Horizon Brief

Source of Truth: management/horizons/H04_Context_Propagation_Across_Commands/README.md

## Problem

Ensure every command runs against the selected corpus context instead of implicit HCO defaults.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for context propagation across commands.

## Success Criteria

- Route repo root, horizons dir, generated dir, locks, and events through CommandContext.
- Include selected corpus in JSON/text output.
- Preserve explicit path overrides for scripts.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
