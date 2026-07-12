# H07 Target Model

Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md

## Target Behavior

Remove HCO branding assumptions from generic parsing and rendering while keeping HCO documents compatible.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/parser.py
- src/horizon_manager/model.py
- tests/test_horizon_model.py

## Implemented Model

- Horizon ids may include a generic leading brand segment before `Hxx`, for example `HM-H07`, while still normalizing to `H07`.
- Horizon titles remove generic branded id prefixes and preserve plain generic document titles.
- Dependency extraction accepts generic branded references and collapses repeated normalized dependency sources.
- Empty horizon directories produce an explicit parse warning instead of silent success.
