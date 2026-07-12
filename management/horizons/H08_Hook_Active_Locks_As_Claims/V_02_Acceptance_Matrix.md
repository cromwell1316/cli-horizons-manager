# H08 Acceptance Matrix

Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Merge explicit --claim values with active lock-store claims. | `python3 -m pytest tests/test_horizon_hooks.py` | [x] |
| A2 | Preserve strict foreign owned-file blocking. | `python3 -m pytest tests/test_horizon_hooks.py` | [x] |
| A3 | Cover CLI and interactive hook flows with tests. | `python3 -m pytest tests/test_horizon_hooks.py tests/test_horizon_interactive.py tests/test_horizon_cli.py` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
