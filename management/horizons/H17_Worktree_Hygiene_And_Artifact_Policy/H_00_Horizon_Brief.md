# H17 Horizon Brief

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

## Problem

Stop operational artifacts and unrelated corpus files from blocking ordinary Horizon Manager landing workflows.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for worktree hygiene and artifact policy.

## Outcome

Completed. The application now documents its worktree hygiene policy and ignores local
runtime, graph, and detector artifacts that should not enter normal app commits.

## Success Criteria

- Define tracked, ignored, and separately landed artifacts. Complete.
- Keep graphify-out and deep-audit outputs out of normal app commits unless scoped.
  Complete.
- Document cleanup and staging discipline. Complete.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
