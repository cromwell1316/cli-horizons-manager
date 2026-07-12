# H06 Horizon Brief

Source of Truth: management/horizons/H06_Corpus_Scoped_Generated_Outputs/README.md

## Problem

Make every generated output land beside the selected corpus instead of HCO-only defaults.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for corpus scoped generated outputs.

## Success Criteria

- Route state, doctor, conflicts, locks, events, dashboard, DAG, and history outputs through corpus context.
- Remove runtime dependence on HCO module DEFAULT_OUTPUT paths.
- Keep standalone module CLIs compatible through explicit output arguments.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
