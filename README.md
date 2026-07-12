# Horizon Manager

Owner: agent-toolchain
Lifecycle: planned
Document Class: subproject

## Purpose
Horizon Manager is the external application for reading, validating, coordinating, and
rendering management horizon corpora. It is not bound to one project checkout.

It is packaged as `cli-horizons-manager` and exposes the `horizon-manager` console
command. The managed projects remain separate repositories or working trees; this
application only receives a selected corpus path and writes generated horizon artifacts
for that selected corpus.

## Scope
- List and select configured horizon corpora.
- Parse horizon README files into canonical state.
- Validate dependency and metadata health.
- Detect file ownership conflicts.
- Track active horizon locks.
- Recommend next safe work.
- Append horizon lifecycle events.
- Provide CLI, dashboard, daemon, watcher, and hook integrations in later horizons.

## Console Interface

The supported local console entry point is `horizon-manager`. From a WSL shell, install
the editable checkout once:

```bash
cd ~/projects/shared/GeoForge/management/subprojects/horizon-manager
python3 -m pip install --user -e .
```

Then launch it directly:

```bash
horizon-manager
```

Launching without arguments opens the keyboard-first selector:

```text
[0] Corpora
[1] Overview / Next Horizons
[2] Refresh State + Doctor + Conflicts
[3] Claim Horizon
[4] Release Horizon
[5] Events
[6] Hook Check
[7] Help
[x] Exit
```

Direct commands remain available for scripts and fast paths:

```bash
horizon-manager next --limit 5
horizon-manager --corpus geoforge next --limit 5
horizon-manager --corpus cli-profile-manager state
horizon-manager claim H54 --agent manual --dry-run
horizon-manager hook --mode manual --claim H53
```

From Windows, the same checkout is reachable through the WSL UNC path:

```text
\\wsl.localhost\Ubuntu\home\olivercromwell\projects\shared\GeoForge\management\subprojects\horizon-manager
```

Run the command itself inside WSL so path expansion, file locks, and generated artifact
paths use Linux filesystem semantics.

## Project Layout
- `pyproject.toml` - external package metadata and console entry point.
- `src/horizon_manager/` - application package.
- `management/horizons/` - this application's own management horizon corpus.
- `tests/` - application tests.

`horizons` is the canonical directory name for horizon corpora. The historical
misspelling `horizonts` is retained only as a deprecated compatibility alias for
hook and watcher path classification; new corpora and documentation should use
`horizons`.

## Managed Corpora
The default registry includes these corpora for the local operator environment:
- `hco` -> `~/projects/shared/GeoForge/management/subprojects/hermes-consistency-orchestrator/horizons`
- `cli-profile-manager` -> `~/projects/shared/cli-profile-manager/management/horizons`
- `geoforge` -> `~/projects/shared/GeoForge/management/horizons`
- `horizon-manager` -> `~/projects/shared/GeoForge/management/subprojects/horizon-manager/management/horizons`

Generated outputs are written next to the selected corpus, under that corpus'
management directory or subproject root. Project-specific runtime paths must enter the
application through one of these mechanisms:

- select a configured corpus with `--corpus`;
- inspect configured corpora with `horizon-manager corpora`;
- override an invocation explicitly with `--repo-root`, `--horizons-dir`, or
  `--generated-dir`.

No managed corpus is treated as the owner of this application.

## Boundary
This project owns the manager application code. It reads managed horizon documents and
writes declared generated outputs only. It must not mutate decisions, contracts, or
deep-audit detector reports.

The package boundary is:

- application code: `src/horizon_manager/`;
- CLI entry point: `horizon-manager`;
- distribution name: `cli-horizons-manager`;
- self-management corpus: `management/horizons/`;
- managed-project data: selected only through the corpus registry or explicit CLI path
  overrides.

## Worktree Hygiene
Normal Horizon Manager commits should contain authored application files, tests,
documentation, and self-management horizon documents. Runtime output and external
detector material are treated as operational artifacts unless a horizon explicitly owns
them.

Tracked by default:
- package metadata, source code, tests, README files, and horizon phase/verification
  documents;
- durable configuration that belongs to this application, such as corpus registry
  configuration when it is intentionally added;
- policy documentation that explains operator behavior.

Ignored by default:
- local Python caches and editable-install metadata;
- `graphify-out/` knowledge graph output;
- `deep_audit/` detector output;
- regenerated `horizon_*.json`, `horizon_*.jsonl`, dashboard/DAG HTML, and
  `horizon_snapshots/` artifacts at the repo root or under `management/`.

Separately landed:
- generated artifacts from another managed corpus;
- deep-audit findings, decisions, contracts, or remediation records;
- graph refresh output when the task is specifically to update graph artifacts.

Before committing, inspect `git status --short` and stage only files owned by the
current horizon. If generated output is deliberately part of a scoped task, use an
explicit force-add and record that exception in the horizon evidence. Unrelated dirty
files should remain unstaged and be treated as another operator's work.
