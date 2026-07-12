# H15 Target Model

Source of Truth: management/horizons/H15_Horizonts_Alias_And_Typo_Cleanup/README.md

## Target Behavior

Resolve the accidental horizonts spelling support by formalizing or removing it.

## Implemented Model

- `horizons` is the canonical corpus directory name.
- `horizonts` remains supported as a deprecated compatibility alias in hook and watcher path classification.
- Alias support is explicit through exported canonical/alias constants in `hooks.py` and `watch.py`.
- New documentation points operators to `horizons`.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/hooks.py
- src/horizon_manager/watch.py
- tests/test_horizon_hooks.py
- tests/test_horizon_watch.py
- README.md
