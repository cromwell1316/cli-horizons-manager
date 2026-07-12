# H08 Target Model

Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md

## Target Behavior

Make Hook Check treat active locks for the current agent as effective claims.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/hooks.py
- management/subprojects/horizon-manager/src/horizon_manager/cli.py
- management/subprojects/horizon-manager/tests/test_horizon_hooks.py
