# H13 Target Model

Source of Truth: management/horizons/H13_Daemon_And_Watcher_Multi_Corpus/README.md

## Target Behavior

Teach daemon and watcher contracts to operate over selected or registered corpora.

## Implemented Model

- `DaemonConfig` carries corpus name, title, repo root, horizons dir, and generated dir metadata.
- Daemon state sync includes a stable `metadata` object, and `/metadata` exposes it through the read-only endpoint surface.
- Watch configs may receive registered corpora and derive watched repo roots deterministically.
- `plan_corpus_refresh` produces per-corpus refresh plans so one watcher batch can route work to the correct corpus.
- Daemon host validation remains localhost-only.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/server.py
- src/horizon_manager/watch.py
- tests/test_horizon_server.py
- tests/test_horizon_watch.py
