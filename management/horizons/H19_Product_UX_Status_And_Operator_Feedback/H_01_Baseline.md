# H19 Baseline

Source of Truth: management/horizons/H19_Product_UX_Status_And_Operator_Feedback/README.md

## Baseline State

Before H19, the interactive menu showed only corpus name and horizons directory. The
dashboard had overview metrics, but no explicit operator feedback rows for doctor,
hook, or preflight status.

## Closed Gaps

- Interactive header now includes active corpus, horizon status counts, lock counts,
  doctor diagnostics, and dirty worktree status.
- Doctor, hook, and preflight interactive commands now emit concise deterministic
  summaries.
- Dashboard rendering now includes an `operator-feedback` section.

## Baseline Checks

- Run `horizon-manager --horizons-dir management/horizons state`.
- Run `horizon-manager --horizons-dir management/horizons doctor`.
- Inspect changed files against the README owned-file list.
