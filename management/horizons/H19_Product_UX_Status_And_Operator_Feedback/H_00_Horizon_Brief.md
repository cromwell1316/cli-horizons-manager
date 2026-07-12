# H19 Horizon Brief

Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md

## Problem

Improve operator feedback so corpus state and next actions are visible without reading raw JSON.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for product ux status and operator feedback.

## Success Criteria

- Show active corpus, horizon counts, lock counts, and dirty status.
- Render concise doctor/hook/preflight summaries.
- Keep keyboard-first interaction script-friendly.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
