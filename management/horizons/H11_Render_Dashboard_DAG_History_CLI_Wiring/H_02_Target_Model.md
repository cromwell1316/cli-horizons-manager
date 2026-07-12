# H11 Target Model

Source of Truth: management/horizons/H11_Render_Dashboard_DAG_History_CLI_Wiring/README.md

## Target Behavior

Replace the render CLI stub with real dashboard, DAG, and history render commands scoped to the selected corpus.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/cli.py
- management/subprojects/horizon-manager/src/horizon_manager/render.py
- management/subprojects/horizon-manager/src/horizon_manager/dag_render.py
- management/subprojects/horizon-manager/src/horizon_manager/history.py
- management/subprojects/horizon-manager/tests/test_horizon_render.py
- management/subprojects/horizon-manager/tests/test_horizon_dag_render.py
- management/subprojects/horizon-manager/tests/test_horizon_history.py
