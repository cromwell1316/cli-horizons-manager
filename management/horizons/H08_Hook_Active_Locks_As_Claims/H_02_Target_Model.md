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

- src/horizon_manager/hooks.py
- tests/test_horizon_hooks.py
- tests/test_horizon_interactive.py

## Implemented Model

- Effective hook claims are the deterministic union of explicit `--claim` values and active lock-store claims for the current agent.
- Expired or foreign-owned active locks are not accepted as current-agent claims.
- Preflight checks use the same effective claim set so hook diagnostics and landing scope checks stay aligned.
- Interactive Hook Check continues to call `hook --mode manual`, relying on the CLI to read lock-store claims.
