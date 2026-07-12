# H13 Target Model

Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md

## Target Behavior

Teach daemon and watcher contracts to operate over selected or registered corpora.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/src/horizon_manager/server.py
- management/subprojects/horizon-manager/src/horizon_manager/watch.py
- management/subprojects/horizon-manager/tests/test_horizon_server.py
- management/subprojects/horizon-manager/tests/test_horizon_watch.py
