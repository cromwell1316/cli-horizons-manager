# H01 Implementation Evidence

Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md

## Status

Completed. H01 package and documentation boundary is implemented.

## Commands

- [x] `python3 -m horizon_manager.cli --corpus horizon-manager state`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h01_state.json`
- [x] `python3 -m pytest`

## Notes

- `pyproject.toml` now uses distribution name `cli-horizons-manager`, describes the
  package as an external keyboard-first CLI, and links the standalone GitHub repository.
- `README.md` documents the external application boundary, WSL install path, UNC path,
  selected-corpus runtime rule, and package/entry-point boundary.
- `src/horizon_manager/__init__.py` no longer describes the package as GeoForge-owned.
- `src/horizon_manager/parser.py` now normalizes records under the current checkout
  relative to the standalone repository root.
- `tests/test_horizon_model.py` covers nested standalone path normalization.
- Self-management corpus parser and doctor verification pass.
