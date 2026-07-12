# H04 Target Model

Source of Truth: management/horizons/H04_Context_Propagation_Across_Commands/README.md

## Target Behavior

Ensure every command runs against the selected corpus context instead of implicit HCO defaults.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/cli.py
- tests/test_horizon_cli.py
