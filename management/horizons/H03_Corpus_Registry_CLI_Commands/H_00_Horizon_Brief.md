# H03 Horizon Brief

Source of Truth: management/horizons/H03_Corpus_Registry_CLI_Commands/README.md

## Problem

Expose corpus registry inspection and management through the CLI.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for corpus registry cli commands.

## Success Criteria

- Add corpus list/doctor surfaces.
- Show horizon counts and path health for every corpus.
- Keep mutation commands explicit and reversible.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
