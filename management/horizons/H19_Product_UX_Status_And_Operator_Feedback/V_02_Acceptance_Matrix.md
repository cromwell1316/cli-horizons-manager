# H19 Acceptance Matrix

Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Show active corpus, horizon counts, lock counts, and dirty status. | `python3 -m pytest tests/test_horizon_interactive.py` | [x] |
| A2 | Render concise doctor/hook/preflight summaries. | `python3 -m pytest tests/test_horizon_interactive.py tests/test_horizon_render.py` | [x] |
| A3 | Keep keyboard-first interaction script-friendly. | focused test review of one-line summaries | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --horizons-dir management/horizons doctor` | [x] |
