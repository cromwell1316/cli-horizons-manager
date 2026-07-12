# H15 Acceptance Matrix

Source of Truth: management/horizons/H15_Horizonts_Alias_And_Typo_Cleanup/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Decide whether horizonts is an official alias. | README and target model review | [x] |
| A2 | Update hook/watch tests and README to match the decision. | `python3 -m pytest tests/test_horizon_hooks.py tests/test_horizon_watch.py` | [x] |
| A3 | Remove stale typo directories if not official. | `find . -type d -name '*horizont*' -not -path './.git/*' -print` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
