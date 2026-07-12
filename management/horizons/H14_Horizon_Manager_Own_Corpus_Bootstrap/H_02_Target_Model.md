# H14 Target Model

Source of Truth: management/horizons/H14_Horizon_Manager_Own_Corpus_Bootstrap/README.md

## Target Behavior

Make Horizon Manager manage its own improvement backlog through this corpus.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/management/horizons/
