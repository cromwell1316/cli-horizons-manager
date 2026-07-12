# H20 Risk Register

Source of Truth: management/horizons/H20_Multi_Corpus_Release_Gate/README.md

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep | The horizon edits adjacent behavior outside its owned files | Mitigated: H20 edits only README and H20 evidence files |
| False green | Tests pass but selected corpus behavior is not exercised | Mitigated: all four configured corpora were parsed and recorded |
| Unsafe mutation | Generated or detector outputs are written into the wrong corpus | Mitigated: H20 runs read-only smoke commands and does not write generated artifacts |
| External corpus diagnostics | Managed corpora outside this repository have doctor failures | Accepted residual risk: H20 records counts and does not mutate external corpora |
| Dependency drift | H16/H18 remain planned while H20 records release evidence | Accepted residual risk: package release gate is recorded separately from those future hardening horizons |
