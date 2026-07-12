# H09 Implementation Evidence

Source of Truth: management/horizons/H09_Hook_Path_Normalization_And_Generated_Classification/README.md

## Status

Implemented.

## Commands

- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h09_state.json`
  - Passed: horizons=20, edges=36, warnings=0, owned_paths=50.
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
  - Passed: diagnostics passed.
- [x] `python3 -m pytest tests/test_horizon_hooks.py`
  - Passed: 16 tests.
- [x] `python3 -m pytest tests/test_horizon_preflight.py tests/test_horizon_cli.py`
  - Passed: 23 tests.
- [x] `python3 -m pytest`
  - Passed: 151 tests.
- [x] `git diff --check`
  - Passed.
- [x] `graphify update .`
  - Passed: graph updated.

## Notes

- Hook path normalization now converts absolute and WSL UNC paths under the selected repo root to repo-relative POSIX paths.
- Generated-output classification is scoped to the selected generated directory instead of the historical HCO-only path.
- CLI hook execution passes corpus `repo_root` and `generated_dir` to the hook runtime.
