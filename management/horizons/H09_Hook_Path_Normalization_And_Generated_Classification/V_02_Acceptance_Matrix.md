# H09 Acceptance Matrix

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Normalize changed paths against the selected repo root. | test/document review | [ ] |
| A2 | Classify horizon_*.json/jsonl/html relative to selected generated dir. | test/document review | [ ] |
| A3 | Remove HCO-only generated path checks from runtime behavior. | test/document review | [ ] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `horizon-manager --horizons-dir management/horizons doctor` | [ ] |
