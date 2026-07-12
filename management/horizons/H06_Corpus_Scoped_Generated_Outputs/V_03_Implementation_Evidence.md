# H06 Implementation Evidence

Source of Truth: management/horizons/H06_Corpus_Scoped_Generated_Outputs/README.md

## Status

Completed. H06 corpus-scoped generated output defaults are implemented.

## Commands

- [x] `python3 -m pytest tests/test_horizon_model.py tests/test_horizon_conflicts.py tests/test_horizon_locks.py tests/test_horizon_render.py tests/test_horizon_dag_render.py tests/test_horizon_history.py`
- [x] `python3 -m horizon_manager.parser --horizons-dir management/horizons --output /tmp/hm_h06_state.json`
- [x] `python3 -m horizon_manager.conflicts --horizons-dir management/horizons --output /tmp/hm_h06_conflicts.json`
- [x] `python3 -m horizon_manager.dag_render --horizons-dir management/horizons --output /tmp/hm_h06_dag.html`
- [x] `python3 -m horizon_manager.cli --corpus horizon-manager doctor`
- [x] `python3 -m pytest`

## Notes

- Parser defaults now use `management/horizons` and `management/horizon_state.json`
  under the standalone project root.
- Conflicts, locks, dashboard, DAG, and history defaults now write under this
  repository's `management/` directory.
- Standalone module CLIs keep explicit output compatibility; parser, conflicts, and DAG
  were verified with `/tmp` output targets.
- Regression tests assert generated-output defaults do not point at
  `hermes-consistency-orchestrator`.
