# H18 Target Model

Source of Truth: management/horizons/H18_Deep_Audit_Boundary_In_Hooks_And_Land/README.md

## Target Behavior

Make detector-output boundaries explicit in hook and land behavior.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/hooks.py
- management/subprojects/horizon-manager/src/horizon_manager/land.py
- management/subprojects/horizon-manager/tests/test_horizon_hooks.py
- management/subprojects/horizon-manager/tests/test_horizon_land.py
