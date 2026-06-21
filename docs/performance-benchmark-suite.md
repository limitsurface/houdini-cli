# Houdini CLI Performance Benchmark Suite

Date: 2026-06-21

Use `scripts/perf_benchmark_suite.py` for broad live-session timing. The suite
talks to a running Houdini session, discovers the current selected node, and
runs representative CLI commands across session, discovery, traversal, node,
parameter, and HDA surfaces.

## Quick Run

```text
uv run python scripts/perf_benchmark_suite.py --iterations 3
```

To keep a report:

```text
uv run python scripts/perf_benchmark_suite.py \
  --iterations 5 \
  --json-out work/perf/benchmark.json \
  --markdown-out work/perf/benchmark.md
```

The generated reports are intentionally suitable for local comparison rather
than CI gating. Timings include process startup, RPyC connection setup, command
execution, JSON serialization, and stdout capture.

## Risky Probes

By default the suite avoids broad/full snapshot probes. Include them when the
session is disposable or the selected node is safe to inspect:

```text
uv run python scripts/perf_benchmark_suite.py --include-risky
```

Risky probes currently include:

- `node get <selected> --section parms`
- `node get <selected> --section full`
- `hda definitions --namespace Scy --max 50 --sections`

These are not necessarily bugs. They are explicit broader reads that should
remain visible in perf reports.

## Thresholds

The default concern thresholds are:

- `slow`: median runtime at or above 750 ms
- `very_slow`: max runtime at or above 1500 ms
- `failure`: any failed or timed-out run

Override them when testing smaller or larger scenes:

```text
uv run python scripts/perf_benchmark_suite.py --slow-ms 500 --very-slow-ms 1000
```

## Current Live Baseline

Baseline from Houdini 21.0.729 with selected node:

```text
/obj/geo1/copnet1/ntsc_hou1
```

Default suite, two iterations:

```text
hda definitions Scy:        median ~346 ms
hda inspect selected:       median ~252 ms
nodetype list cop:          median ~233 ms
node get selected:          median ~225 ms
recipe list:                median ~205 ms
node parms list selected:   median ~190 ms
shelf list/find:            median ~155-162 ms
```

Risky suite, two iterations:

```text
hda definitions Scy --sections: median ~527 ms
hda definitions Scy:            median ~336 ms
node get selected --section full:  median ~181 ms
node get selected --section parms: median ~179 ms
```

No default-threshold concerns were observed in this fixture after the
2026-06-21 batching passes.

## Static Audit Companion

After running the live benchmark, run:

```text
uv run python scripts/audit_perf_hotspots.py
```

Current static findings are mostly explicit-heavy or targeted surfaces, not
new broad discovery misses:

- `hda validate --cook` and OpenCL validation/sync can force cooks.
- `node get --section parms` and `node get --section full` intentionally use
  broad HOM snapshot APIs.
- HDA/parameter mutation commands use `parmTemplateGroup()` and
  `setParmTemplateGroup()` because they edit interfaces.
- OpenCL SOP/DOP validation still has targeted binding row readers that should
  be benchmarked separately if those workflows become active.

Treat these as review prompts. A static finding becomes a performance concern
when the live suite, a focused probe, or dogfooding shows slow runtime,
timeouts, large output, crashes, or surprising implicit cooks.

## Related Deep Probes

Use the focused scripts when investigating a specific command family:

```text
uv run python scripts/perf_probe_opencl_cop.py
uv run python scripts/perf_probe_hda_parms.py
uv run python scripts/perf_probe_node_get.py
uv run python scripts/audit_perf_hotspots.py
```

`audit_perf_hotspots.py` is static and heuristic; it finds suspicious code
patterns, not measured slow commands.
