# H09 Target Model

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

## Target Behavior

Make hook classification correct for every corpus and for generated outputs.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/hooks.py
- management/subprojects/horizon-manager/tests/test_horizon_hooks.py
