# HM-H07 Generic Horizon Parser And Branding

Owner: agent-toolchain
Source of Truth: management/horizons/H07_Generic_Horizon_Parser_And_Branding/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 3).

## Purpose

Remove HCO branding assumptions from generic parsing and rendering while keeping HCO documents compatible.

## Goals

- Accept generic Hxx documents as first-class input.
- Keep HCO-Hxx title normalization backward compatible.
- Make empty corpus diagnostics clear.

## Files

- H_00_Horizon_Brief.md
- H_01_Baseline.md
- H_02_Target_Model.md
- H_03_Workstreams.md
- H_04_Governance_And_Safety_Boundaries.md
- V_00_Validation_Plan.md
- V_01_Risk_Register.md
- V_02_Acceptance_Matrix.md
- V_03_Implementation_Evidence.md

## Owned Files (EXCLUSIVE)

- `src/horizon_manager/parser.py`
- `src/horizon_manager/model.py`
- `tests/test_horizon_model.py`

## Completion Notes

- `HorizonId` accepts generic branded horizon prefixes such as `HM-H07` and keeps `HCO-H07` compatibility.
- README title parsing strips any supported branded prefix before rendering the generic title.
- Dependency parsing recognizes branded `after`, `depends on`, and `Needs:` references without duplicating the same normalized dependency source.
- Empty corpus discovery returns a clear `no_readmes` warning naming the inspected directory.

## Concurrency

Wave 3. Needs: H01/H02.
