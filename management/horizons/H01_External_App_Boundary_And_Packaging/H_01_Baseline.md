# H01 Baseline

Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md

## Current State

The current Horizon Manager implementation does not yet fully satisfy this horizon's target behavior. Existing tests may cover adjacent contracts, but this horizon requires focused implementation evidence.

## Known Gaps

- The implementation needs corpus-aware behavior where applicable.
- Operator output must be deterministic and script-friendly.
- Tests must cover the owned files before the horizon can land.

## Baseline Checks

- Run `horizon-manager --horizons-dir management/horizons state`.
- Run `horizon-manager --horizons-dir management/horizons doctor`.
- Inspect changed files against the README owned-file list.
