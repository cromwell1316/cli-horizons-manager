# H04 Acceptance Matrix

Source of Truth: management/horizons/H04_Context_Propagation_Across_Commands/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Route repo root, horizons dir, generated dir, locks, and events through CommandContext. | test/document review | [x] |
| A2 | Include selected corpus in JSON/text output. | test/document review | [x] |
| A3 | Preserve explicit path overrides for scripts. | test/document review | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `horizon-manager --horizons-dir management/horizons doctor` | [x] |
