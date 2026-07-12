# H07 Target Model

Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md

## Target Behavior

Remove HCO branding assumptions from generic parsing and rendering while keeping HCO documents compatible.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/parser.py
- management/subprojects/horizon-manager/src/horizon_manager/model.py
- management/subprojects/horizon-manager/tests/test_horizon_model.py
