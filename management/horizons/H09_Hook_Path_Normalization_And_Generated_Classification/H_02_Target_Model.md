# H09 Target Model

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

## Target Behavior

Make hook classification correct for every corpus and for generated outputs.

## Implemented Model

- `HookContext` stores the selected repo root and generated directory, then normalizes changed paths to deterministic repo-relative POSIX paths.
- Hook generated-output classification is scoped to the selected generated directory and direct `horizon_*.json`, `horizon_*.jsonl`, and `horizon_*.html` artifacts.
- CLI hook execution passes the active corpus repo root and generated directory into hook classification.
- HCO-specific generated path checks were removed from runtime classification.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/hooks.py
- tests/test_horizon_hooks.py
- src/horizon_manager/cli.py
