# H13 Horizon Brief

Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md

## Problem

Teach daemon and watcher contracts to operate over selected or registered corpora.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for daemon and watcher multi corpus.

## Success Criteria

- Add corpus metadata to daemon state and refresh endpoints.
- Watch registered corpus roots with corpus-scoped refresh plans.
- Keep localhost-only daemon safety.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
