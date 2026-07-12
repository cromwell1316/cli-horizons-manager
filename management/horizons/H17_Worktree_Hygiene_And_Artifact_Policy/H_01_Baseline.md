# H17 Baseline

Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md

## Baseline State

Before this horizon, `.gitignore` ignored Python caches, editable-install metadata, and
`graphify-out/`, but it did not document or ignore Horizon Manager runtime artifacts or
deep-audit detector output.

## Closed Gaps

- Runtime `horizon_*` files at the repo root and under `management/` are ignored.
- `deep_audit/` detector output is ignored unless explicitly force-added for a scoped
  task.
- README explains tracked, ignored, and separately landed artifact classes.

## Baseline Checks

- Run `horizon-manager --horizons-dir management/horizons state`.
- Run `horizon-manager --horizons-dir management/horizons doctor`.
- Inspect changed files against the README owned-file list.
