# H19 Risk Register

Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep | The horizon edits adjacent behavior outside its owned files | Mitigated: changes are limited to H19 owned implementation and test files |
| False green | Tests pass but selected corpus behavior is not exercised | Mitigated: focused tests exercise interactive status and dashboard feedback |
| Unsafe mutation | Generated or detector outputs are written into the wrong corpus | Mitigated: H19 only reads state/locks/git status and does not add new write paths |
| Noisy operator output | Extra summaries make scripted interaction harder to parse | Mitigated: summaries are deterministic one-line `summary:` records and JSON CLI output remains unchanged |
