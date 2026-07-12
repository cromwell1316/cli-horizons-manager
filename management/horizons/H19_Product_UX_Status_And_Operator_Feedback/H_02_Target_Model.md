# H19 Target Model

Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md

## Target Behavior

Improve operator feedback so corpus state and next actions are visible without reading raw JSON.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/interactive.py
- management/subprojects/horizon-manager/src/horizon_manager/render.py
- management/subprojects/horizon-manager/tests/test_horizon_interactive.py
- management/subprojects/horizon-manager/tests/test_horizon_render.py
