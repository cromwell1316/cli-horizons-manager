# H09 Acceptance Matrix

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Normalize changed paths against the selected repo root. | `python3 -m pytest tests/test_horizon_hooks.py` | [x] |
| A2 | Classify horizon_*.json/jsonl/html relative to selected generated dir. | `python3 -m pytest tests/test_horizon_hooks.py` | [x] |
| A3 | Remove HCO-only generated path checks from runtime behavior. | `python3 -m pytest tests/test_horizon_hooks.py` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
