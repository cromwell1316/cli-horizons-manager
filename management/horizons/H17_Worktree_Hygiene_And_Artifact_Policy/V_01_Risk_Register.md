# H17 Risk Register

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Scope creep | The horizon edits adjacent behavior outside its owned files | Mitigated: changes are limited to `.gitignore`, README, and H17 evidence files |
| False green | Tests pass but selected corpus behavior is not exercised | Mitigated: self-management corpus parse/doctor checks are recorded |
| Unsafe mutation | Generated or detector outputs are written into the wrong corpus | Mitigated: no runtime mutation behavior changed; ignored artifact paths are documented |
| Hidden required artifact | An ignore rule hides a file that should be reviewed | Mitigated: generated or detector artifacts can still be explicitly force-added when a horizon owns them |
