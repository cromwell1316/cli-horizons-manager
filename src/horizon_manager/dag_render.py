"""Generated horizon dependency DAG renderer."""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import html
import json
from pathlib import Path
from typing import Any

from .model import HorizonId, HorizonRecord, HorizonState, HorizonStatus


DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "hermes-consistency-orchestrator/horizon_dependency_graph.html"


@dataclass(frozen=True, order=True)
class DagNode:
    id: HorizonId
    title: str
    status: str
    wave: int
    depth: int
    row: int
    start_now: bool = False
    owned_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", HorizonId(self.id))
        object.__setattr__(self, "owned_files", tuple(sorted(str(path) for path in self.owned_files)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "title": self.title,
            "status": self.status,
            "wave": self.wave,
            "depth": self.depth,
            "row": self.row,
            "start_now": self.start_now,
            "owned_files": list(self.owned_files),
        }


@dataclass(frozen=True, order=True)
class DagEdge:
    source: HorizonId
    target: HorizonId
    kind: str = "depends_on"
    cross_wave: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", HorizonId(self.source))
        object.__setattr__(self, "target", HorizonId(self.target))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "target": str(self.target),
            "kind": self.kind,
            "cross_wave": self.cross_wave,
        }


@dataclass(frozen=True)
class DagLayout:
    columns: tuple[int, ...]
    wave_counts: dict[int, int]
    max_depth: int
    max_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": list(self.columns),
            "wave_counts": {str(key): self.wave_counts[key] for key in sorted(self.wave_counts)},
            "max_depth": self.max_depth,
            "max_rows": self.max_rows,
        }


@dataclass(frozen=True)
class DagModel:
    nodes: tuple[DagNode, ...]
    edges: tuple[DagEdge, ...]
    layout: DagLayout
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(sorted(self.nodes, key=lambda item: (item.wave, item.depth, item.row, item.id.number))))
        object.__setattr__(self, "edges", tuple(sorted(self.edges, key=lambda item: (item.source.number, item.target.number, item.kind))))
        object.__setattr__(self, "metadata", _stable_value(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "layout": self.layout.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def build_dag_model(state: HorizonState, conflicts: Any = None, locks: Any = None) -> DagModel:
    del conflicts
    implemented = {record.id for record in state.records if record.status is HorizonStatus.IMPLEMENTED}
    active_locked = _active_locked_horizons(locks)
    depths = _dependency_depths(state)
    rows_by_wave: dict[int, int] = {}
    nodes: list[DagNode] = []
    for record in sorted(state.records, key=lambda item: ((item.wave or 10_000), depths.get(item.id, 0), item.id.number)):
        wave = record.wave or 0
        row = rows_by_wave.get(wave, 0)
        rows_by_wave[wave] = row + 1
        nodes.append(
            DagNode(
                id=record.id,
                title=record.title,
                status=record.status.value,
                wave=wave,
                depth=depths.get(record.id, 0),
                row=row,
                start_now=_can_start(record, implemented, active_locked),
                owned_files=tuple(path.path for path in record.owned_files),
            )
        )

    records = {record.id: record for record in state.records}
    edges: list[DagEdge] = []
    seen: set[tuple[HorizonId, HorizonId]] = set()
    for record in state.records:
        for dependency in record.dependencies:
            if dependency.id not in records:
                continue
            key = (record.id, dependency.id)
            if key in seen:
                continue
            seen.add(key)
            source = record.id
            target = dependency.id
            edges.append(
                DagEdge(
                    source=source,
                    target=target,
                    cross_wave=(records[source].wave or 0) != (records[target].wave or 0),
                )
            )
    waves = tuple(sorted(rows_by_wave))
    layout = DagLayout(
        columns=waves,
        wave_counts={wave: rows_by_wave[wave] for wave in waves},
        max_depth=max(depths.values(), default=0),
        max_rows=max(rows_by_wave.values(), default=0),
    )
    return DagModel(
        nodes=tuple(nodes),
        edges=tuple(edges),
        layout=layout,
        metadata={
            "generated_from": state.generated_from,
            "horizon_count": len(state.records),
            "edge_count": len(edges),
        },
    )


def render_dag_html(model: DagModel) -> str:
    payload = json.dumps(model.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    nodes = "\n".join(_render_node(node) for node in model.nodes)
    wave_headers = "\n".join(_render_wave_header(wave, model.layout.wave_counts[wave]) for wave in model.layout.columns)
    legend = _legend()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HCO Horizon Dependency DAG</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f7f9f5;
  --panel: #ffffff;
  --ink: #172018;
  --muted: #5f6f61;
  --line: #9dad9c;
  --edge: #6f806f;
  --cross: #b77912;
  --accent: #4A7850;
  --planned: #9eaa9f;
  --start: #c9820f;
  --shadow: rgba(23, 32, 24, .12);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    color-scheme: dark;
    --bg: #111611;
    --panel: #192119;
    --ink: #edf4ea;
    --muted: #aab7a7;
    --line: #465346;
    --edge: #8aa08a;
    --cross: #e0a337;
    --accent: #7fb183;
    --planned: #7f8b7f;
    --start: #f0b347;
    --shadow: rgba(0, 0, 0, .28);
  }}
}}
:root[data-theme="light"] {{ color-scheme: light; --bg: #f7f9f5; --panel: #ffffff; --ink: #172018; --muted: #5f6f61; --line: #9dad9c; --edge: #6f806f; --cross: #b77912; --accent: #4A7850; --planned: #9eaa9f; --start: #c9820f; --shadow: rgba(23, 32, 24, .12); }}
:root[data-theme="dark"] {{ color-scheme: dark; --bg: #111611; --panel: #192119; --ink: #edf4ea; --muted: #aab7a7; --line: #465346; --edge: #8aa08a; --cross: #e0a337; --accent: #7fb183; --planned: #7f8b7f; --start: #f0b347; --shadow: rgba(0, 0, 0, .28); }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  overflow-x: hidden;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
}}
.toolbar {{
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(8px);
}}
h1 {{ margin: 0; font-size: 18px; line-height: 1.2; }}
.meta {{ color: var(--muted); font-size: 12px; }}
button {{ border: 1px solid var(--line); background: var(--panel); color: var(--ink); padding: 7px 10px; border-radius: 6px; }}
.legend {{ display: flex; gap: 14px; align-items: center; flex-wrap: wrap; padding: 10px 18px; border-bottom: 1px solid var(--line); color: var(--muted); }}
.legend span {{ display: inline-flex; gap: 6px; align-items: center; }}
.sample {{ width: 24px; height: 12px; border: 2px solid var(--accent); border-radius: 3px; }}
.sample.planned {{ border-color: var(--planned); border-style: dashed; }}
.sample.start {{ border-color: var(--start); }}
.sample.edge {{ height: 0; border: 0; border-top: 2px solid var(--edge); }}
.sample.cross {{ height: 0; border: 0; border-top: 2px dashed var(--cross); }}
.graph-scroll {{
  overflow-x: auto;
  overflow-y: visible;
  width: 100%;
  padding: 18px;
}}
.graph {{
  position: relative;
  min-width: max-content;
  padding: 34px 18px 60px;
}}
.waves {{
  display: grid;
  grid-template-columns: repeat({len(model.layout.columns)}, 260px);
  gap: 54px;
  margin-bottom: 10px;
}}
.wave-title {{
  color: var(--muted);
  font-weight: 700;
  border-bottom: 2px solid var(--line);
  padding-bottom: 6px;
}}
.nodes {{
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat({len(model.layout.columns)}, 260px);
  grid-auto-rows: minmax(92px, auto);
  gap: 18px 54px;
  align-items: start;
}}
.node {{
  min-height: 82px;
  padding: 12px 14px;
  border: 3px solid var(--accent);
  border-radius: 7px;
  background: color-mix(in srgb, var(--panel) 90%, var(--accent));
  box-shadow: 0 8px 18px var(--shadow);
}}
.node[data-status="planned"] {{ border-color: var(--planned); border-style: dashed; background: var(--panel); }}
.node[data-start="true"] {{ border-color: var(--start); }}
.node-id {{ font-weight: 800; font-size: 13px; }}
.node-title {{
  margin-top: 7px;
  font-weight: 700;
  line-height: 1.25;
  overflow-wrap: anywhere;
}}
.node-meta {{ margin-top: 7px; color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }}
.badge {{
  float: right;
  margin-left: 8px;
  border: 2px solid currentColor;
  border-radius: 999px;
  padding: 1px 6px;
  color: var(--start);
  font-size: 10px;
  font-weight: 700;
}}
.edges {{ position: absolute; inset: 0; z-index: 1; pointer-events: none; overflow: visible; }}
.edges path {{ fill: none; stroke: var(--edge); stroke-width: 2; opacity: .72; }}
.edges path.cross-wave {{ stroke: var(--cross); stroke-dasharray: 6 5; }}
</style>
</head>
<body>
<div class="toolbar">
  <div><h1>HCO Horizon Dependency DAG</h1><div class="meta">{len(model.nodes)} horizons · {len(model.edges)} dependencies · generated from canonical state</div></div>
  <button id="themeToggle" type="button">Theme: auto</button>
</div>
{legend}
<main class="graph-scroll" id="graphScroll">
  <section class="graph" id="graph">
    <svg class="edges" id="edges" aria-hidden="true"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--edge)"></path></marker><marker id="arrowCross" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--cross)"></path></marker></defs></svg>
    <div class="waves">{wave_headers}</div>
    <div class="nodes">{nodes}</div>
  </section>
</main>
<script id="dagData" type="application/json">{html.escape(payload)}</script>
<script>
const model = JSON.parse(document.getElementById('dagData').textContent);
const graph = document.getElementById('graph');
const svg = document.getElementById('edges');
function drawEdges() {{
  const graphRect = graph.getBoundingClientRect();
  svg.setAttribute('width', graph.scrollWidth);
  svg.setAttribute('height', graph.scrollHeight);
  svg.querySelectorAll('path.edge-path').forEach(path => path.remove());
  for (const edge of model.edges) {{
    const source = document.querySelector(`[data-node-id="${{edge.source}}"]`);
    const target = document.querySelector(`[data-node-id="${{edge.target}}"]`);
    if (!source || !target) continue;
    const a = source.getBoundingClientRect();
    const b = target.getBoundingClientRect();
    const x1 = a.left + a.width - graphRect.left;
    const y1 = a.top + a.height / 2 - graphRect.top;
    const x2 = b.left - graphRect.left;
    const y2 = b.top + b.height / 2 - graphRect.top;
    const dx = Math.max(48, Math.abs(x2 - x1) * .45);
    const d = `M ${{x1}} ${{y1}} C ${{x1 + dx}} ${{y1}}, ${{x2 - dx}} ${{y2}}, ${{x2}} ${{y2}}`;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('class', `edge-path${{edge.cross_wave ? ' cross-wave' : ''}}`);
    path.setAttribute('marker-end', edge.cross_wave ? 'url(#arrowCross)' : 'url(#arrow)');
    svg.appendChild(path);
  }}
}}
const themes = ['auto', 'light', 'dark'];
let themeIndex = 0;
document.getElementById('themeToggle').addEventListener('click', () => {{
  themeIndex = (themeIndex + 1) % themes.length;
  const theme = themes[themeIndex];
  document.documentElement.toggleAttribute('data-theme', theme !== 'auto');
  if (theme !== 'auto') document.documentElement.dataset.theme = theme;
  document.getElementById('themeToggle').textContent = `Theme: ${{theme}}`;
  requestAnimationFrame(drawEdges);
}});
new ResizeObserver(drawEdges).observe(graph);
new MutationObserver(drawEdges).observe(document.documentElement, {{ attributes: true, attributeFilter: ['data-theme'] }});
window.addEventListener('resize', drawEdges);
window.addEventListener('load', drawEdges);
requestAnimationFrame(drawEdges);
</script>
</body>
</html>
"""


def write_dag(path: str | Path, html_text: str) -> None:
    Path(path).write_text(html_text, encoding="utf-8")


def _render_node(node: DagNode) -> str:
    column = node.wave + 1
    row = node.row + 1
    title = html.escape(node.title)
    owned = ", ".join(node.owned_files[:2])
    if len(node.owned_files) > 2:
        owned += f" +{len(node.owned_files) - 2}"
    badge = '<span class="badge">start</span>' if node.start_now else ""
    return (
        f'<article class="node" data-node-id="{node.id}" data-status="{html.escape(node.status)}" '
        f'data-start="{str(node.start_now).lower()}" style="grid-column:{column};grid-row:{row};">'
        f'{badge}<div class="node-id">{node.id}</div><div class="node-title">{title}</div>'
        f'<div class="node-meta">wave {node.wave} · depth {node.depth} · {html.escape(node.status)}</div>'
        f'<div class="node-meta">{html.escape(owned or "no owned files")}</div></article>'
    )


def _render_wave_header(wave: int, count: int) -> str:
    return f'<div class="wave-title">Wave {wave}<div class="meta">{count} horizons</div></div>'


def _legend() -> str:
    return (
        '<div class="legend">'
        '<span><i class="sample"></i>shipped</span>'
        '<span><i class="sample planned"></i>planned</span>'
        '<span><i class="sample start"></i>can start now</span>'
        '<span><i class="sample edge"></i>depends-on</span>'
        '<span><i class="sample cross"></i>cross-wave</span>'
        "</div>"
    )


def _dependency_depths(state: HorizonState) -> dict[HorizonId, int]:
    records = {record.id: record for record in state.records}
    memo: dict[HorizonId, int] = {}

    def depth(horizon_id: HorizonId, seen: frozenset[HorizonId] = frozenset()) -> int:
        if horizon_id in memo:
            return memo[horizon_id]
        if horizon_id in seen or horizon_id not in records:
            return 0
        deps = [dependency.id for dependency in records[horizon_id].dependencies if dependency.id in records]
        value = 0 if not deps else 1 + max(depth(dep, seen | {horizon_id}) for dep in deps)
        memo[horizon_id] = value
        return value

    for record in state.records:
        depth(record.id)
    return memo


def _can_start(record: HorizonRecord, implemented: set[HorizonId], active_locked: set[HorizonId]) -> bool:
    if record.status is not HorizonStatus.PLANNED:
        return False
    if record.id in active_locked:
        return False
    return all(dependency.id in implemented for dependency in record.dependencies)


def _active_locked_horizons(locks: Any) -> set[HorizonId]:
    if locks is None:
        return set()
    rows = []
    if isinstance(locks, dict):
        rows = locks.get("locks") or locks.get("active_locks") or []
    else:
        rows = getattr(locks, "locks", locks if isinstance(locks, (list, tuple)) else [])
    result: set[HorizonId] = set()
    for row in rows:
        status = _get(row, "status", "active")
        if str(getattr(status, "value", status)).lower() not in {"active", "claimed", "running"}:
            continue
        raw_id = _get(row, "horizon_id", None) or _get(row, "id", None)
        if raw_id is not None:
            result.add(HorizonId(raw_id))
    return result


def _get(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _stable_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HCO horizon dependency DAG HTML.")
    parser.add_argument("--horizons-dir", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    from .parser import DEFAULT_HORIZONS_DIR, parse_horizon_tree

    state = parse_horizon_tree(args.horizons_dir or DEFAULT_HORIZONS_DIR)
    model = build_dag_model(state)
    rendered = render_dag_html(model)
    write_dag(args.output, rendered)
    print(f"wrote {args.output}: nodes={len(model.nodes)} edges={len(model.edges)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
