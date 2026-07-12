# H20 Risk Register

Source of Truth: management/horizons/H20_Multi_Corpus_Release_Gate/README.md

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep | The horizon edits adjacent behavior outside its owned files | Keep changes scoped and add a later horizon for adjacent work |
| False green | Tests pass but selected corpus behavior is not exercised | Add corpus-specific tests or smoke commands |
| Unsafe mutation | Generated or detector outputs are written into the wrong corpus | Route writes through context and verify paths |
