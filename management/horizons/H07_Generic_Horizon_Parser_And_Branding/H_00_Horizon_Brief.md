# H07 Horizon Brief

Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md

## Problem

Remove HCO branding assumptions from generic parsing and rendering while keeping HCO documents compatible.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for generic horizon parser and branding.

## Success Criteria

- Accept generic Hxx documents as first-class input.
- Keep HCO-Hxx title normalization backward compatible.
- Make empty corpus diagnostics clear.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
