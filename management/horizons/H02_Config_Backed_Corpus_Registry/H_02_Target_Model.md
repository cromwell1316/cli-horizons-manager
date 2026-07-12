# H02 Target Model

Source of Truth: management/horizons/H02_Config_Backed_Corpus_Registry/README.md

## Target Behavior

Replace hardcoded project assumptions with a registry that can describe every managed horizon corpus.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/corpus.py
- tests/test_horizon_corpus.py
