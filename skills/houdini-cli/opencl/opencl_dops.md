---
name: houdini-opencl-dops
description: Guidance for Gas OpenCL and GPU microsolvers in DOP networks, including field bindings, parameter synchronization, worksets, and Pyro references.
---

# OpenCL in DOP Workflows

Use this guidance for Gas OpenCL and other GPU microsolvers in DOP networks.
For OpenCL SOP geometry kernels, read `opencl_sops.md`. For Copernicus, read
`../copernicus/copernicus.md`.

## Core Guidance

1. Use the established patterns in this guide directly for routine
   microsolvers. Inspect a relevant shipped node when the operation is
   unfamiliar, solver-specific, synchronization-heavy, or poorly documented.
2. Keep RPC inspection serial. Large DOP networks and unlocked solver HDAs are
   unsafe targets for concurrent HOM/RPyC traversal.
3. After editing a Gas OpenCL kernel, run `opencl sync`, `opencl validate`,
   and `node errors`.
4. Use `@TimeInc` for integration, damping, and decay so behavior remains
   stable across substeps.
5. Keep advection, projection, and other specialized operations in native GPU
   microsolvers when available.

## Gas OpenCL Interface

Gas OpenCL uses a third interface model distinct from COP and SOP OpenCL:

- the binding count is stored in `paramcount`;
- rows use `parameter#Name`, `parameter#Type`, and type-specific fields;
- field bindings refer to named DOP simulation data;
- geometry attributes refer to named Geometry data;
- data-option bindings refer to option values on simulation data.

`houdini-cli opencl sync <node-path>` detects the DOP context and rebuilds
these parameter rows from `#bind` directives.

## Minimal Field Kernel

```c
#bind scalarfield &density float
#bind parm gain float val=0.5

@KERNEL
{
    @density *= @gain;
}
```

Synchronize:

```text
houdini-cli opencl sync /obj/dopnet1/gasopencl1 --clear
houdini-cli opencl validate /obj/dopnet1/gasopencl1
houdini-cli node errors /obj/dopnet1/gasopencl1
```

Sync creates a writable Scalar Field row for `density`, a Float row for
`gain`, and a generated `gain` control linked to the row's value.

## Supported Binding Families

The Houdini binding extractor and CLI adapter support:

| Binding type | Gas OpenCL row |
| :--- | :--- |
| `int`, `float`, `float3`, `float4` | Constant parameter |
| `ramp` | Sampled ramp |
| `scalarfield` | Scalar Field data |
| `vectorfield` | Vector Field data |
| `matrixfield` | Matrix Field data |
| point/primitive/detail bindings | Geometry attribute |
| `volume` | SOP volume primitive in Geometry data |
| `vdb` | VDB primitive in Geometry data |
| `option` | Option value from DOP simulation data |

Gas OpenCL does not expose a Float Vec2 parameter type. Do not use a `float2`
constant binding unless the target node version explicitly supports it.

## Field Bindings

Fields can be readable, writable, or both:

```c
#bind scalarfield density float
#bind scalarfield &temperature float
#bind vectorfield &vel float3
```

Writable fields are marked stale on the CPU and remain on the GPU until
another solver requests them. Avoid `Flush Attributes` unless an immediate
CPU readback is required.

Enable Force Align when a kernel assumes that bound fields share resolution,
transform, and voxel indexing. Without alignment, the kernel must account for
different grids explicitly.

## Geometry, Volumes, and VDBs

Gas OpenCL can bind attributes from named Geometry DOP data:

```c
#bind point geoP float3 geometry=Geometry name=P
```

It can also bind SOP volumes and VDB primitives stored in Geometry data. The
row may request resolution, voxel size, and transforms between voxel and SOP
space.

Use optional bindings and defaults when simulation data may be absent.
Required missing data prevents the microsolver from running.

## Data Options

The Gas OpenCL parameter schema supports option values from named simulation
data, including integer and float tuples. The `#bind option` type is recognized
by Houdini's extractor.

The exact directive modifiers for selecting a non-default DOP data name are
not documented clearly in the prepared help. Inspect a native node or the
generated binding dictionary before relying on guessed syntax.

## Time and Substeps

Gas Substep may invoke a microsolver with a timestep smaller than the frame
timestep. Enable Include Timestep and use `@TimeInc`.

Unlike OpenCL COP/SOP nodes, Gas OpenCL's prepared docs do not expose a
generic kernel `Iterations` option; use Gas Substep or solver-specific
iteration parameters when a DOP microsolver must run repeatedly.

Percentage decay:

```c
float decay = pow(1.0f - clamp(@rate, 0.0f, 1.0f), @TimeInc);
@density *= decay;
```

Fixed subtraction per second:

```c
@density -= @rate * @TimeInc;
```

Half-life:

```c
@density *= pow(0.5f, @TimeInc / max(@halflife, 1e-6f));
```

## Compile-Time Features

Native Gas OpenCL nodes use kernel options to remove disabled features:

```c
#ifdef USECONTROL
    control = fit(@control, @controlmin, @controlmax, 0.0f, 1.0f);
#endif
```

Compile definitions are useful for optional controls, goal values, bounds,
and operation modes. Avoid option strings that vary every timestep because
they can force repeated kernel compilation.

## Worksets

Gas OpenCL supports worksets stored as integer-array detail attributes on
named Geometry data:

- Worksets Begin contains offsets.
- Worksets Length contains dispatch lengths.
- Each nonzero workset is invoked separately by default.

Single-workgroup modes can batch small worksets and define
`SINGLE_WORKGROUP`, `SINGLE_WORKGROUP_SPANS`, or
`SINGLE_WORKGROUP_ALWAYS`. The kernel must synchronize correctly, usually
with `barrier(CLK_MEM_GLOBAL_FENCE)`.

Validate all workset offsets and lengths before dereferencing bound arrays.
Never let only part of a workgroup return before a barrier.

## Minimal Pyro Reference

The Pyro Solver SOP contains a DOP network. Minimal mode is a reduced graph,
not one monolithic OpenCL kernel.

| Node | Pattern |
| :--- | :--- |
| `dopnet1/minimal_source` | GPU VDB source merge |
| `pyro_solver/solver/substep_minimal` | Reduced solver composition |
| `solver/advect_fields_cl` | GPU scalar-field advection |
| `solver/advect_vel_cl` | GPU velocity advection |
| `solver/project_minimal` | Multigrid non-divergent projection |
| `pyro_solver/gasopencl1` | Small field clamp kernel |
| `gasdissipate_density/gasopencl_scalar` | Decay, ramps, compile switches |
| `solver/gasdissipate_temperature/gasopencl_scalar` | Temperature decay |

The minimal graph combines sourcing, advection, forces, dissipation,
divergence handling, and pressure projection inside a substep solver.

## Inspection Workflow

Use serial commands:

```text
houdini-cli node find <dop-root> --name opencl --max-depth 12
houdini-cli node parms list <gas-opencl-node>
houdini-cli parm get <gas-opencl-node>/kernelcode
houdini-cli parm get <gas-opencl-node>/kernelfile
houdini-cli node connections <solver-node>
```

If Use Code Snippet is disabled, inspect `kernelfile` and `kernelname`.

## Common Failure Modes

- Treating Gas OpenCL rows as SOP `bindings#` rows or COP signatures.
- Forgetting to bind a field as writable.
- Assuming fields are aligned when Force Align is disabled.
- Applying fixed decay once per substep instead of using `@TimeInc`.
- Forcing CPU readback with Flush Attributes unnecessarily.
- Recompiling every timestep through changing kernel options.
- Omitting global-ID bounds checks in explicit kernels.
- Incorrect barriers in workset kernels.
- Concurrent RPC inspection of large or unlocked solver networks.

## References

- `../help_prepared/nodes/dop/gasopencl.txt`
- `../help_prepared/vex/ocl.txt`
- Installed OpenCL files under `$HFS/houdini/ocl/`
