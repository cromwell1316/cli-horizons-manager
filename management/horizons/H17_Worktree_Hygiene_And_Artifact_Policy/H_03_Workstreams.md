# H17 Workstreams

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

## WS1 Baseline

Read the owned files and existing tests. Confirm current behavior and failure modes before editing.

Status: complete. Reviewed `.gitignore`, README, H17 files, and current tracked artifact
state.

## WS2 Implementation

Implement the smallest corpus-aware behavior that satisfies the README goals.

Status: complete. Added ignore rules for runtime, graph, and detector artifacts and
documented the worktree hygiene model.

## WS3 Tests

Add or update focused tests for the changed contracts. Prefer existing test modules listed in Owned Files.

Status: complete. Verified ignore behavior with `git check-ignore` and parsed the
self-management corpus.

## WS4 Documentation And Evidence

Update README/help text if operator behavior changes, then record final validation in `V_03_Implementation_Evidence.md`.

Status: complete. README and verification evidence now describe the policy and checks.
