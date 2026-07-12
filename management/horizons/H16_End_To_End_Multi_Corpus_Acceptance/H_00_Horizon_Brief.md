# H16 Horizon Brief

Source of Truth: management/horizons/H16_End_To_End_Multi_Corpus_Acceptance/README.md

## Problem

Prove the app works end-to-end across all configured corpora.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for end to end multi corpus acceptance.

## Success Criteria

- Validate state, doctor, conflicts, next, claim/release, hook, preflight, render, and land paths per corpus.
- Record command evidence for every registered corpus.
- Ensure outputs identify selected corpus.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
