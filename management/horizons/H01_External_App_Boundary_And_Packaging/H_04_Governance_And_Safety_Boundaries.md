# H01 Governance And Safety Boundaries

Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md

## Boundaries

- Do not mutate managed project files outside the selected corpus unless the README explicitly owns them.
- Do not weaken hook, preflight, or land safety to make tests pass.
- Do not write detector outputs, decisions, contracts, or unrelated graph artifacts as part of this horizon.
- Preserve explicit operator bypasses and report them honestly.

## Coordination

This horizon has no upstream horizon dependency.

## Handoff Requirement

Before landing, run the relevant unit tests plus project handoff checks required by AGENTS.md.
