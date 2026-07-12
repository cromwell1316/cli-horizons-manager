# H09 Horizon Brief

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

## Problem

Make hook classification correct for every corpus and for generated outputs.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for hook path normalization and generated classification.

## Success Criteria

- Normalize changed paths against the selected repo root.
- Classify horizon_*.json/jsonl/html relative to selected generated dir.
- Remove HCO-only generated path checks from runtime behavior.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
