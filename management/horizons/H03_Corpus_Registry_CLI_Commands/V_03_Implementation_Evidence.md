# H03 Implementation Evidence

Source of Truth: management/horizons/H03_Corpus_Registry_CLI_Commands/README.md

## Status

Completed. H03 corpus registry CLI commands are implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_cli.py`
- [x] `python3 -m horizon_manager.cli --format json corpora list`
- [x] `python3 -m horizon_manager.cli --format json corpora doctor`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h03_state.json`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m pytest`

## Notes

- `src/horizon_manager/cli.py` now supports `corpora list` and `corpora doctor` while
  preserving `corpora` as a list alias.
- Corpus list output includes `horizon_count`, path-existence fields, `healthy`, and
  per-corpus diagnostics.
- Corpus doctor exits with validation failure and deterministic diagnostic strings when
  registry path health fails.
- H03 adds no mutation command; registry inspection remains read-only.
