# H10 Validation Plan

Source of Truth: management/horizons/H10_Preflight_CLI_Wiring/README.md

## Required Checks

1. Parse the Horizon Manager corpus with `horizon-manager --horizons-dir management/horizons state`.
2. Run `horizon-manager --horizons-dir management/horizons doctor` and confirm no new errors.
3. Run targeted tests for the owned files.
4. Run the full `python3 -m pytest` suite when CLI, hook, lock, render, daemon, or parser contracts change.
5. Run Graphify/CRG/ECC handoff checks before final handoff when repository edits are non-trivial.

## Acceptance Evidence

Record exact commands and outcomes in `V_03_Implementation_Evidence.md`.
