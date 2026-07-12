# H17 Acceptance Matrix

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

| ID | Criterion | Verification | Status |
| --- | --- | --- | --- |
| A1 | Define tracked, ignored, and separately landed artifacts. | README document review | [x] |
| A2 | Keep graphify-out and deep-audit outputs out of normal app commits unless scoped. | `.gitignore` review and `git check-ignore` | [x] |
| A3 | Document cleanup and staging discipline. | README document review | [x] |
| A4 | README, phase files, and verification files remain parseable by Horizon Manager | `python3 -m horizon_manager.cli --horizons-dir management/horizons doctor` | [x] |
