# H16 Target Model

Source of Truth: management/horizons/H16_End_To_End_Multi_Corpus_Acceptance/README.md

## Target Behavior

Prove the app works end-to-end across all configured corpora.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/tests/test_horizon_cli.py
- management/subprojects/horizon-manager/tests/test_horizon_server.py
- management/subprojects/horizon-manager/tests/test_horizon_interactive.py
- management/subprojects/horizon-manager/management/horizons/H16_End_To_End_Multi_Corpus_Acceptance/
