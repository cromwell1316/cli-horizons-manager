# H05 Implementation Evidence

Source of Truth: management/horizons/H05_Interactive_Corpus_Selector/README.md

## Status

Completed. H05 interactive corpus selector is implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_interactive.py`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h05_state.json`
- [x] `python3 -m pytest`

## Notes

- `_default_menu_runner` renders active corpus and selected horizons directory.
- `[0] Corpora` now opens a corpus selector and replaces the active in-session
  `CommandContext`.
- Help uses parser formatting directly, so it no longer exits the interactive loop.
- Interactive tests cover menu header context, corpus switching, and help loop behavior.
