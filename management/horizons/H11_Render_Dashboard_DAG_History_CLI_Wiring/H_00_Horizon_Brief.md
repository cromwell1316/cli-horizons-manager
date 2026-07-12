# H11 Horizon Brief

Source of Truth: management/horizons/H11_Render_Dashboard_DAG_History_CLI_Wiring/README.md

## Problem

Replace the render CLI stub with real dashboard, DAG, and history render commands scoped to the selected corpus.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for render dashboard dag history cli wiring.

## Success Criteria

- Add target flags and output controls.
- Use corpus title and generated dir in artifacts.
- Keep render output deterministic.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
