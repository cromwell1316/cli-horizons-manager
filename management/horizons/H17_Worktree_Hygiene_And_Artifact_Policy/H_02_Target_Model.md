# H17 Target Model

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

## Target Behavior

Stop operational artifacts and unrelated corpus files from blocking ordinary Horizon Manager landing workflows.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/.gitignore
- management/subprojects/horizon-manager/README.md
- management/subprojects/horizon-manager/management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/
