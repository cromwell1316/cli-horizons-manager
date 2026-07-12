# H06 Target Model

Source of Truth: management/horizons/H06_Corpus_Scoped_Generated_Outputs/README.md

## Target Behavior

Make every generated output land beside the selected corpus instead of HCO-only defaults.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/parser.py
- management/subprojects/horizon-manager/src/horizon_manager/conflicts.py
- management/subprojects/horizon-manager/src/horizon_manager/locks.py
- management/subprojects/horizon-manager/src/horizon_manager/render.py
- management/subprojects/horizon-manager/src/horizon_manager/dag_render.py
- management/subprojects/horizon-manager/src/horizon_manager/history.py
