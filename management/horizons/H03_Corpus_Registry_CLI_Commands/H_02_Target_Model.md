# H03 Target Model

Source of Truth: management/horizons/H03_Corpus_Registry_CLI_Commands/README.md

## Target Behavior

Expose corpus registry inspection and management through the CLI.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- src/horizon_manager/cli.py
- tests/test_horizon_cli.py
