# H02 Acceptance Matrix

Source of Truth: management/horizons/H02_Config_Backed_Corpus_Registry/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Load built-in corpora and future configured corpora through one API. | test/document review | [x] |
| A2 | Represent repo root, horizons dir, generated dir, name, and title. | test/document review | [x] |
| A3 | Validate missing or empty corpus paths deterministically. | test/document review | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `horizon-manager --horizons-dir management/horizons doctor` | [x] |
