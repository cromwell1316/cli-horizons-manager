# HM-H17 Worktree Hygiene And Artifact Policy

Owner: agent-toolchain
Source of Truth: management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/README.md
Lifecycle: completed
Document Class: horizon

Status: implemented (Wave 7).

## Purpose

Stop operational artifacts and unrelated corpus files from blocking ordinary Horizon Manager landing workflows.

## Goals

- Define tracked, ignored, and separately landed artifacts. Done in README worktree
  hygiene policy.
- Keep graphify-out and deep-audit outputs out of normal app commits unless scoped.
  Done in `.gitignore` and README policy.
- Document cleanup and staging discipline. Done in README policy and validation
  evidence.

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

- `management/subprojects/horizon-manager/.gitignore`
- `management/subprojects/horizon-manager/README.md`
- `management/subprojects/horizon-manager/management/horizons/H17_Worktree_Hygiene_And_Artifact_Policy/`

## Concurrency

Wave 7. Needs: H12.
