# H02 Horizon Brief

Source of Truth: management/horizons/H02_Config_Backed_Corpus_Registry/README.md

## Problem

Replace hardcoded project assumptions with a registry that can describe every managed horizon corpus.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for config backed corpus registry.

## Success Criteria

- Load built-in corpora and future configured corpora through one API.
- Represent repo root, horizons dir, generated dir, name, and title.
- Validate missing or empty corpus paths deterministically.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
