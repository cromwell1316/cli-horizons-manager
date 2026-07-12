# Horizon Manager

Owner: agent-toolchain
Lifecycle: planned
Document Class: subproject

## Purpose
Horizon Manager is the external application for reading, validating, coordinating, and
rendering management horizon corpora. It is not bound to one project checkout.

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

The supported local console entry point is `horizon-manager`. Install the editable
checkout once:

```bash
python3 -m pip install --user -e management/subprojects/horizon-manager
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

## Project Layout
- `pyproject.toml` - package metadata and console entry placeholder.
- `src/horizon_manager/` - application package.
- `tests/` - application tests.

## Managed Corpora
Configured corpora:
- `hco` -> `~/projects/shared/GeoForge/management/subprojects/hermes-consistency-orchestrator/horizons`
- `cli-profile-manager` -> `~/projects/shared/cli-profile-manager/management/horizons`
- `geoforge` -> `~/projects/shared/GeoForge/management/horizons`
- `horizon-manager` -> `~/projects/shared/GeoForge/management/subprojects/horizon-manager/management/horizons`

Generated outputs are written next to the selected corpus, under its management
directory or subproject root. Use `horizon-manager corpora` to inspect the active
registry.

## Boundary
This project owns the manager application code. It reads managed horizon documents and
writes declared generated outputs only. It must not mutate decisions, contracts, or
deep-audit detector reports.
