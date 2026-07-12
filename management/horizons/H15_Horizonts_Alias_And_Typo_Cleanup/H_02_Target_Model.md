# H15 Target Model

Source of Truth: management/horizons/H15_Horizonts_Alias_And_Typo_Cleanup/README.md

## Target Behavior

Resolve the accidental horizonts spelling support by formalizing or removing it.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/hooks.py
- management/subprojects/horizon-manager/src/horizon_manager/watch.py
- management/subprojects/horizon-manager/tests/test_horizon_hooks.py
- management/subprojects/horizon-manager/tests/test_horizon_watch.py
- management/subprojects/horizon-manager/README.md
