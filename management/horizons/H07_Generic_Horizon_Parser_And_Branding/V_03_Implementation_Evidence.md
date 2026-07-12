# H07 Implementation Evidence

Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md

## Status

Implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_model.py`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h07_state.json`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m pytest`

## Notes

- `HorizonId` now accepts generic branded ids while preserving HCO branded ids.
- Parser title normalization strips generic branded prefixes before storing the title.
- Dependency extraction supports branded `after`, `depends on`, and `Needs:` references and deduplicates repeated normalized sources.
- Empty corpus parsing records a `no_readmes` warning with the inspected directory path.
