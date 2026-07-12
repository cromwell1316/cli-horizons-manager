# H13 Acceptance Matrix

Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Add corpus metadata to daemon state and refresh endpoints. | `python3 -m pytest tests/test_horizon_server.py` | [x] |
| A2 | Watch registered corpus roots with corpus-scoped refresh plans. | `python3 -m pytest tests/test_horizon_watch.py` | [x] |
| A3 | Keep localhost-only daemon safety. | `python3 -m pytest tests/test_horizon_server.py` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
