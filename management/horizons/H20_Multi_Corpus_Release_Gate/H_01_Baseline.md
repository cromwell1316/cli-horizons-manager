# H20 Baseline

Source of Truth: management/horizons/H20_Multi_Corpus_Release_Gate/README.md

## Baseline State

Before H20, implementation horizons had landed across packaging, registry, CLI,
interactive UX, hooks, preflight, land, rendering, daemon/watch, worktree hygiene, and
operator feedback. The project still needed one consolidated release gate documenting
package tests, corpus smoke checks, handoff gates, and residual external-corpus risks.

## Closed Gaps

- Full package tests are recorded in implementation evidence.
- All configured corpora are parsed by the external application.
- Registry, self-management doctor, Graphify, CRG, and ECC handoff gates are recorded.
- External corpus doctor failures are captured as residual managed-corpus risks.

## Baseline Checks

- Run `horizon-manager --horizons-dir management/horizons state`.
- Run `horizon-manager --horizons-dir management/horizons doctor`.
- Inspect changed files against the README owned-file list.
