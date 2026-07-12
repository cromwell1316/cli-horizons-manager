# H02 Implementation Evidence

Source of Truth: management/horizons/H02_Config_Backed_Corpus_Registry/README.md

## Status

Completed. H02 config-backed corpus registry is implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_corpus.py`
- [x] `python3 -m pytest tests/test_horizon_cli.py`
- [x] `python3 -m horizon_manager.cli --format json corpora`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h02_state.json`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m pytest`

## Notes

- `src/horizon_manager/corpus.py` now exposes `builtin_corpora`, `load_corpora`,
  `known_corpora`, `resolve_corpus`, and `validate_corpus_paths`.
- Optional TOML config is loaded from an explicit path or
  `HORIZON_MANAGER_CORPORA_CONFIG`; built-ins remain the default registry.
- `tests/test_horizon_corpus.py` covers built-ins, configured corpora, env config,
  duplicate names, missing required fields, resolve errors, and deterministic path
  diagnostics.
- Full test suite passes with 127 tests.
