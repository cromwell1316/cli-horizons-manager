"""Capstone workflow contracts for Horizon Mission Control.

H54 composes the H39-H53 contracts without taking ownership of their internals.
The helpers here are deliberately deterministic so docs, tests, and the eventual CLI
can agree on the same operator sequence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


REQUIRED_HORIZONS = tuple(f"H{number}" for number in range(39, 54))
CAPSTONE_SEQUENCE = ("next", "claim", "doctor", "preflight", "land", "release", "render")
HORIZON_ROOT = "management/subprojects/hermes-consistency-orchestrator"
REQUIRED_SURFACES = ("CLI", "daemon", "watcher", "hooks", "dashboard", "DAG", "time machine")


@dataclass(frozen=True)
class MissionControlStep:
    """One operator-visible capstone step."""

    step_id: str
    command: str
    required_inputs: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    blocks_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", str(self.step_id).strip())
        object.__setattr__(self, "command", str(self.command).strip())
        object.__setattr__(self, "required_inputs", tuple(sorted(str(item) for item in self.required_inputs)))
        object.__setattr__(self, "expected_outputs", tuple(sorted(str(item) for item in self.expected_outputs)))
        object.__setattr__(self, "blocks_on", tuple(sorted(str(item) for item in self.blocks_on)))
        if not self.step_id:
            raise ValueError("step_id is required")
        if not self.command:
            raise ValueError("command is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "command": self.command,
            "required_inputs": list(self.required_inputs),
            "expected_outputs": list(self.expected_outputs),
            "blocks_on": list(self.blocks_on),
        }


@dataclass(frozen=True)
class MissionControlPlan:
    """Deterministic H54 capstone plan."""

    steps: tuple[MissionControlStep, ...]
    required_horizons: tuple[str, ...] = REQUIRED_HORIZONS
    generated_artifacts: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(sorted(self.steps, key=lambda item: item.step_id)))
        object.__setattr__(self, "required_horizons", tuple(sorted(str(item) for item in self.required_horizons)))
        object.__setattr__(self, "generated_artifacts", tuple(sorted(str(item) for item in self.generated_artifacts)))
        object.__setattr__(self, "diagnostics", tuple(sorted(str(item) for item in self.diagnostics)))

    @property
    def commands(self) -> tuple[str, ...]:
        return tuple(step.command for step in self.steps)

    @property
    def blocking_horizons(self) -> tuple[str, ...]:
        return tuple(sorted({horizon for step in self.steps for horizon in step.blocks_on}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "commands": list(self.commands),
            "required_horizons": list(self.required_horizons),
            "blocking_horizons": list(self.blocking_horizons),
            "generated_artifacts": list(self.generated_artifacts),
            "diagnostics": list(self.diagnostics),
            "steps": [step.to_dict() for step in self.steps],
        }


def build_capstone_plan(
    state: Mapping[str, object] | None = None,
    *,
    root: str = HORIZON_ROOT,
) -> MissionControlPlan:
    """Build the canonical H54 operator plan.

    `state` is accepted for the future implementation path; the current contract keeps
    ordering independent from runtime state so docs and tests stay stable.
    """

    _ = state
    artifacts = (
        f"{root}/horizon_state.json",
        f"{root}/horizon_doctor.json",
        f"{root}/horizon_conflicts.json",
        f"{root}/horizon_locks.json",
        f"{root}/horizon_next.json",
        f"{root}/horizon_preflight.json",
        f"{root}/horizon_events.jsonl",
        f"{root}/horizon_dashboard.html",
        f"{root}/horizon_dependency_graph.html",
        f"{root}/horizon_snapshots/",
        f"{root}/HORIZON_MISSION_CONTROL.md",
    )
    steps = (
        MissionControlStep(
            "01-next",
            "next",
            required_inputs=(f"{root}/horizons/",),
            expected_outputs=(f"{root}/horizon_next.json",),
            blocks_on=("H43",),
        ),
        MissionControlStep(
            "02-claim",
            "claim",
            required_inputs=(f"{root}/horizon_locks.json",),
            expected_outputs=(f"{root}/horizon_locks.json",),
            blocks_on=("H42", "H45"),
        ),
        MissionControlStep(
            "03-doctor",
            "doctor",
            required_inputs=(f"{root}/horizon_state.json",),
            expected_outputs=(f"{root}/horizon_doctor.json",),
            blocks_on=("H39", "H45"),
        ),
        MissionControlStep(
            "04-preflight",
            "preflight",
            required_inputs=(f"{root}/horizon_conflicts.json",),
            expected_outputs=(f"{root}/horizon_preflight.json",),
            blocks_on=("H41", "H46"),
        ),
        MissionControlStep(
            "05-land",
            "land",
            required_inputs=(f"{root}/horizon_preflight.json",),
            expected_outputs=(f"{root}/horizon_events.jsonl",),
            blocks_on=("H47",),
        ),
        MissionControlStep(
            "06-release",
            "release",
            required_inputs=(f"{root}/horizon_locks.json",),
            expected_outputs=(f"{root}/horizon_locks.json", f"{root}/horizon_events.jsonl"),
            blocks_on=("H42", "H44", "H45"),
        ),
        MissionControlStep(
            "07-render",
            "render",
            required_inputs=(f"{root}/horizon_state.json", f"{root}/horizon_events.jsonl"),
            expected_outputs=(
                f"{root}/horizon_dashboard.html",
                f"{root}/horizon_dependency_graph.html",
                f"{root}/horizon_snapshots/",
            ),
            blocks_on=("H48", "H49", "H50", "H51", "H52", "H53"),
        ),
    )
    return MissionControlPlan(steps=steps, generated_artifacts=artifacts)


def validate_capstone_readiness(
    plan: MissionControlPlan,
    *,
    horizons_dir: Path,
) -> tuple[bool, tuple[str, ...]]:
    """Validate that required horizon source contracts are present."""

    diagnostics: list[str] = []
    commands = plan.commands
    if commands != CAPSTONE_SEQUENCE:
        diagnostics.append("capstone sequence mismatch: " + " -> ".join(commands))
    if len({step.step_id for step in plan.steps}) != len(plan.steps):
        diagnostics.append("duplicate capstone step id")
    if len(set(commands)) != len(commands):
        diagnostics.append("duplicate capstone command")
    for horizon in plan.required_horizons:
        matches = sorted(horizons_dir.glob(f"{horizon}_*/README.md"))
        if not matches:
            diagnostics.append(f"missing horizon contract: {horizon}")
    unknown_blockers = sorted(set(plan.blocking_horizons) - set(plan.required_horizons))
    for horizon in unknown_blockers:
        diagnostics.append(f"unknown blocking horizon: {horizon}")
    required_artifacts = {
        "horizon_state.json",
        "horizon_doctor.json",
        "horizon_conflicts.json",
        "horizon_locks.json",
        "horizon_next.json",
        "horizon_preflight.json",
        "horizon_events.jsonl",
        "horizon_dashboard.html",
        "horizon_dependency_graph.html",
        "horizon_snapshots/",
        "HORIZON_MISSION_CONTROL.md",
    }
    artifact_names = {Path(path.rstrip("/")).name + ("/" if path.endswith("/") else "") for path in plan.generated_artifacts}
    for artifact in sorted(required_artifacts - artifact_names):
        diagnostics.append(f"missing generated artifact: {artifact}")
    if not any(path.endswith("HORIZON_MISSION_CONTROL.md") for path in plan.generated_artifacts):
        diagnostics.append("missing capstone runbook artifact")
    return not diagnostics, tuple(diagnostics)


def render_operator_runbook(plan: MissionControlPlan) -> str:
    """Render the planned operator runbook body."""

    lines = [
        "# Horizon Mission Control",
        "",
        "Owner: agent-toolchain",
        "Source of Truth: management/subprojects/hermes-consistency-orchestrator/horizons/H54_Horizon_Mission_Control_Capstone/README.md",
        "Lifecycle: living",
        "Document Class: operator runbook",
        "",
        "This runbook is generated from the H54 capstone workflow contract. It is the operator model for coordinating parallel horizon agents through the external Horizon Manager project.",
        "",
        "## Canonical Workflow",
    ]
    for step in plan.steps:
        inputs = ", ".join(step.required_inputs) or "none"
        outputs = ", ".join(step.expected_outputs) or "none"
        blockers = ", ".join(step.blocks_on) or "none"
        lines.append(f"{int(step.step_id.split('-', 1)[0])}. `{step.command}`")
        lines.append(f"   - inputs: {inputs}")
        lines.append(f"   - outputs: {outputs}")
        lines.append(f"   - contracts: {blockers}")
    lines.extend(
        [
            "",
            "## Required Surfaces",
            "- CLI: operator command entry point for `next`, `claim`, `doctor`, `preflight`, `land`, `release`, and `render`.",
            "- Daemon: localhost-only state gateway with readonly mode by default.",
            "- Watcher: explicit refresh planning for horizon files, locks, events, dashboard, DAG, and time-machine snapshots.",
            "- Hooks: local checks that report and block using the same preflight semantics as manual operation.",
            "- Dashboard: current view of state, locks, conflicts, next work, events, and since-last changes.",
            "- DAG: dependency graph for horizon sequencing and cross-wave visibility.",
            "- Time machine: append-only snapshot and diff view between renders.",
            "",
            "## Generated Artifacts",
        ]
    )
    for artifact in plan.generated_artifacts:
        lines.append(f"- {artifact}")
    lines.extend(
        [
            "",
            "## Parallel-Agent Rules",
            "- Claim a horizon before editing its exclusive owned files.",
            "- Commit only files owned by the claimed horizon or explicitly shared generated outputs.",
            "- Treat unrelated dirty files as another agent's work unless the owner explicitly says otherwise.",
            "- Run preflight before land and render after successful landing.",
            "- Release stale claims explicitly; do not silently overwrite another agent's claim.",
            "",
            "## Recovery",
            "- Stale lock: inspect the lock owner, event log, and active worktree before release.",
            "- Failed preflight: fix the reported owned-file, dependency, or evidence issue before trying land again.",
            "- Hook rejection: run the same preflight manually and keep the hook output as evidence.",
            "- Stale dashboard, DAG, or snapshot summary: rerun render after source truth is healthy.",
            "",
            "## Safety",
            "Hooks report and block; they do not auto-stage, auto-commit, or auto-push. They also do not format or rewrite authored files. Daemon/watch mode may refresh generated outputs only through documented commands and must not mutate source horizon files silently.",
            "",
            "## H54 Boundary",
            "This runbook composes H39-H53. It does not redefine their internal contracts or take ownership of their implementation files.",
        ]
    )
    return "\n".join(lines) + "\n"
