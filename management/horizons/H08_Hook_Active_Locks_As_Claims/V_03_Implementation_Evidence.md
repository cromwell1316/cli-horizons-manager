# H08 Implementation Evidence

Source of Truth: management/horizons/H08_Hook_Active_Locks_As_Claims/README.md

## Status

Implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_hooks.py`
- [x] `python3 -m pytest tests/test_horizon_interactive.py`
- [x] `python3 -m pytest tests/test_horizon_cli.py`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h08_state.json`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m pytest`

## Notes

- Hook diagnostics use active same-agent locks as effective claims.
- Foreign active locks continue to produce unclaimed and foreign owned-file diagnostics.
- CLI hook checks load `horizon_locks.json` automatically through the existing command context.
- Interactive Hook Check delegates to CLI hook mode so it inherits the same lock-store claim behavior.
