# H20 Target Model

Source of Truth: management/horizons/H20_Multi_Corpus_Release_Gate/README.md

## Target Behavior

Create the final release gate proving Horizon Manager is ready as an external multi-corpus application.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/management/horizons/H20_Multi_Corpus_Release_Gate/
- management/subprojects/horizon-manager/README.md
