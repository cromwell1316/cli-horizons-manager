# H20 Acceptance Matrix

Source of Truth: management/horizons/H20_Multi_Corpus_Release_Gate/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Run full tests and corpus smoke checks. | `python3 -m pytest`; `state`/`doctor`/`next` smoke commands | [x] |
| A2 | Run Graphify, CRG, and ECC handoff gates. | `graphify update .`; `./scripts/crg.sh handoff`; `./scripts/ecc.sh handoff` | [x] |
| A3 | Record final evidence and residual risks. | `V_03_Implementation_Evidence.md` review | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --horizons-dir management/horizons doctor` | [x] |
