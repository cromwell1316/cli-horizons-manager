# H11 Target Model

Source of Truth: management/horizons/H11_Render_Dashboard_DAG_History_CLI_Wiring/README.md

## Target Behavior

Replace the render CLI stub with real dashboard, DAG, and history render commands scoped to the selected corpus.

## Implemented Model

- CLI `render` accepts repeatable `--target` values for `dashboard`, `dag`, `history`, and `all`.
- `--output` controls a single dashboard or DAG render target; history uses `--snapshot-dir`.
- Default render output paths are under the selected corpus generated directory.
- Dashboard and DAG HTML titles use the selected corpus title.
- History snapshots include corpus name, corpus title, and generated directory metadata.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/cli.py
- src/horizon_manager/render.py
- src/horizon_manager/dag_render.py
- src/horizon_manager/history.py
- tests/test_horizon_render.py
- tests/test_horizon_dag_render.py
- tests/test_horizon_history.py
- tests/test_horizon_cli.py
