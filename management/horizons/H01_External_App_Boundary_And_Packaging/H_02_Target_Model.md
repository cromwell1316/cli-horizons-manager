# H01 Target Model

Source of Truth: management/horizons/H01_External_App_Boundary_And_Packaging/README.md

## Target Behavior

Make Horizon Manager explicitly external to any one managed project, with package metadata and operator documentation that do not imply HCO ownership.

## Required Properties

- Deterministic CLI and JSON behavior.
- Corpus-scoped paths and generated outputs where runtime state is involved.
- Backward compatibility for existing HCO corpus workflows unless explicitly superseded.
- Clear diagnostics when required input is missing or unsafe.

## Owned Implementation Surface

- management/subprojects/horizon-manager/pyproject.toml
- management/subprojects/horizon-manager/README.md
- management/subprojects/horizon-manager/src/horizon_manager/__init__.py
