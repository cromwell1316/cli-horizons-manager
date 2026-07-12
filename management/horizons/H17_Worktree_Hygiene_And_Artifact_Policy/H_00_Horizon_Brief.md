# H17 Horizon Brief

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

## Problem

Stop operational artifacts and unrelated corpus files from blocking ordinary Horizon Manager landing workflows.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for worktree hygiene and artifact policy.

## Success Criteria

- Define tracked, ignored, and separately landed artifacts.
- Keep graphify-out and deep-audit outputs out of normal app commits unless scoped.
- Document cleanup and staging discipline.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
