# H10 Target Model

Source of Truth: management/horizons/H10_Preflight_CLI_Wiring/README.md

## Target Behavior

Replace the preflight CLI stub with the real preflight implementation over selected corpus state.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/cli.py
- management/subprojects/horizon-manager/src/horizon_manager/preflight.py
- management/subprojects/horizon-manager/tests/test_horizon_cli.py
- management/subprojects/horizon-manager/tests/test_horizon_preflight.py
