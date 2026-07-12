# H06 Acceptance Matrix

Source of Truth: management/horizons/H06_Corpus_Scoped_Generated_Outputs/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Route state, doctor, conflicts, locks, events, dashboard, DAG, and history outputs through corpus context. | test/document review | [ ] |
| A2 | Remove runtime dependence on HCO module DEFAULT_OUTPUT paths. | test/document review | [ ] |
| A3 | Keep standalone module CLIs compatible through explicit output arguments. | test/document review | [ ] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `horizon-manager --horizons-dir management/horizons doctor` | [ ] |
