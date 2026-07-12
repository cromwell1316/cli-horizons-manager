# H07 Acceptance Matrix

Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Accept generic Hxx documents as first-class input. | `python3 -m pytest tests/test_horizon_model.py` | [x] |
| A2 | Keep HCO-Hxx title normalization backward compatible. | `python3 -m pytest tests/test_horizon_model.py` | [x] |
| A3 | Make empty corpus diagnostics clear. | `python3 -m pytest tests/test_horizon_model.py` | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --corpus horizon-manager doctor` | [x] |
