# H11 Acceptance Matrix

Source of Truth: management/horizons/H11_Render_Dashboard_DAG_History_CLI_Wiring/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Add target flags and output controls. | `python3 -m pytest tests/test_horizon_cli.py` | [x] |
| A2 | Use corpus title and generated dir in artifacts. | `python3 -m pytest tests/test_horizon_cli.py tests/test_horizon_render.py tests/test_horizon_dag_render.py tests/test_horizon_history.py` | [x] |
| A3 | Keep render output deterministic. | `python3 -m pytest tests/test_horizon_render.py tests/test_horizon_dag_render.py tests/test_horizon_history.py` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
