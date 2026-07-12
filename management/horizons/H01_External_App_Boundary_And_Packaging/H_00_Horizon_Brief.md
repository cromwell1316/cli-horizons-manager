# H01 Horizon Brief

Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md

## Problem

Make Horizon Manager explicitly external to any one managed project, with package metadata and operator documentation that do not imply HCO ownership.

## Desired Outcome

Horizon Manager has a clear, testable implementation increment for external app boundary and packaging.

## Success Criteria

- Define the external application boundary in README and package metadata.
- Keep project-specific runtime paths behind corpus selection.
- Document install and WSL usage for an external operator tool.

## Scope

This horizon owns only the files listed in the README. Shared behavior outside those files is consumed read-only unless a later coordination horizon expands ownership.
