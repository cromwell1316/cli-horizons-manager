# H05 Target Model

Source of Truth: management/horizons/H05_Interactive_Corpus_Selector/README.md

## Target Behavior

Make the keyboard-first console safe for multi-corpus operation.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/interactive.py
- tests/test_horizon_interactive.py
