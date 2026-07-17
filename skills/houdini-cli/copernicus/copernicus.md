---
name: houdini-copernicus-opencl
description: Specialized guidance for Houdini Copernicus and OpenCL kernel development, including verified coordinate-space rules, bindings, sampling, reusable patterns, and live CLI inspection.
---

# Houdini Copernicus and OpenCL

Use this guidance when developing GPU-accelerated Copernicus filters, procedural textures, deformations, or solvers.

## Core Mandates

1. **Read and apply the coordinate rules below every time.** Coordinate-space mistakes can produce plausible but fundamentally incorrect results.
2. **Inspect native kernels.** Use [kernel_reference_index.md](kernel_reference_index.md) to find relevant nodes, create them in Houdini, locate their internal OpenCL nodes, and read `kernelcode`.
3. **Prefer OpenCL for complex per-pixel work.** Keeping Copernicus processing on the GPU avoids unnecessary transfers.
4. **Use `#bind` and `@KERNEL`.** Do not manually author the generated kernel signature.
5. **After editing a kernel, run `houdini-cli opencl sync <node-path>`**, then validate and check node errors before judging the output.

## Inspection Guidance

Prefer direct COP data inspection over viewport screenshots when debugging pixel values.

- Use `houdini-cli cop info` for cooked layer metadata and `houdini-cli cop sample` for point samples.
- For full-frame or data-buffer inspection, export a raw EXR through the CLI and analyze the file with external tools instead of printing large buffers through the CLI or agent context.
- Raw EXR inspection examples should mention orientation explicitly: OpenCV/NumPy arrays are commonly top-origin, while comparisons to Houdini COP pixel coordinates may need Y-coordinate mapping.
- If the user's shell Python lacks NumPy, use the `hython` executable shipped with their Houdini install. Do not assume a fixed install path, operating system layout, or Houdini version; locate the user's Houdini installation and run NumPy-based summary scripts with its bundled Python.

## Critical: Spaces and Coordinates

**This section is mandatory context for every Copernicus OpenCL task. Do not write sampling, warping, shape, grid, or pixel code from memory without applying these rules.**

### Image Space

`@P` is centered, aspect-aware image space:

- `(0, 0)` is the image center.
- Image-space units are square when pixel aspect ratio is `1`.
- The longest image dimension spans approximately `-1` to `1`.
- The shorter dimension has a proportionally smaller range.

At `640x360`, pixel centers span approximately:

```text
X: -0.9984 to 0.9984
Y: -0.5609 to 0.5609
```

Do **not** multiply `@P.x` by `@xres / @yres` for aspect correction. `@P` is already aspect-aware; `length(@P)` produces a circle on a non-square image.

### Sampling and Bindings

Use a normal layer binding for IMX accessors:

```c
#bind layer src
#bind layer !&dst

@KERNEL
{
    float4 color = @src.imageSample(@P);
    @dst.set(color);
}
```

`@src` is shorthand for `@src.imageSample(@P)`.

The `!` modifier requests a raw OpenCL image binding. `#bind layer !src` does **not** expose IMX methods such as `.imageSample()`, `.bufferIndex()`, or coordinate transforms.

Coordinate-specific accessors:

| Coordinates | Access |
| :--- | :--- |
| Image space | `@src.imageSample(float2)` or `@src` at `@P` |
| Texture space | `@src.textureSample(float2)` |
| Floating-point buffer space | `@src.bufferSample(float2)` |
| Integer buffer space | `@src.bufferIndex(int2)` |

Do not assume `@P * 0.5f + 0.5f` converts image space to texture space on non-square images. Use transforms:

```c
float2 uv = @src.bufferToTexture(@src.imageToBuffer(@P));
```

### Discrete Pixel Math

`@ixy` is an `int2` from `(0, 0)` to `@res - 1`. Use it for grids, blocks, pixelation, and exact pixel access:

```c
int2 snappedIxy = (@ixy / @pixel_size) * @pixel_size;
int2 sampleIxy = snappedIxy + (int2)(@pixel_size / 2);
sampleIxy = clamp(sampleIxy, (int2)(0, 0), @res - 1);
float4 color = @src.bufferIndex(sampleIxy);
```

Integer pixel math produces square pixel blocks regardless of image dimensions. Center sampling avoids boundary ambiguity; clamping prevents invalid indexed access.

## Binding Symbols

| Symbol | Meaning | Example |
| :--- | :--- | :--- |
| None | IMX layer binding with sampling, indexing, metadata, and transforms | `#bind layer src` |
| `!` | Raw OpenCL image binding | `#bind layer !src` |
| `&` | Writable binding | `#bind layer &dst` |
| `?` | Optional binding; test with `#if @name.bound` | `#bind layer mask?` |
| `!&` | Writable raw image, commonly used for aligned output | `#bind layer !&dst` |

### Layer Types and Defaults

OpenCL COP layer binds can force the generated COP input or output type by
adding a type token after the layer name and modifiers. This was verified in
Houdini 21.0.729 with a fresh OpenCL COP:

| COP type | `#bind` token | Example |
| :--- | :--- | :--- |
| ID | `int` | `#bind layer id? int` |
| Mono | `float` | `#bind layer depth? float` |
| UV | `float2` | `#bind layer uv? float2` |
| RGB | `float3` | `#bind layer rgb? float3` |
| RGBA | `float4` | `#bind layer rgba? float4` |

The same suffix works for writable outputs:

```c
#bind layer depth? float val=0
#bind layer !&depth_out float
```

For optional typed layer inputs, `val=` supplies real default layer data when
the input is unwired:

```c
#bind layer mask? float val=0.5
#bind layer uv? float2 val={0.25, 0.75}
#bind layer color? float3 val={0.1, 0.2, 0.3}
#bind layer plate? float4 val={0.1, 0.2, 0.3, 1}
```

Prefer explicit types when relying on `val=` defaults. In live tests,
unconnected typed optional inputs sampled these defaults directly. Geometry,
Metadata, and VDB output/input type tokens were not confirmed through
`#bind layer`; attempts such as `geo`, `ivdb`, `fvdb`, `vvdb`, and `fnvdb`
left generated signatures as Varying Layer and should be treated as unknown
until separately verified.

### Parameter Defaults

For scalar/vector controls, declare OpenCL parameters with an explicit `val=`
default:

```c
#bind parm scale float val=0.1
#bind parm samples int val=17
#bind parm tint float3 val={1, 0.8, 0.5}
```

After `houdini-cli opencl sync <node-path> --clear`, the OpenCL COP creates
spare controls from these `#bind parm` directives and wires binding values to
those controls. Bare declarations such as `#bind parm scale float` initialize
the generated control to `0`, which can make a kernel appear broken even though
the bindings are valid.

Use `options_iterations` to re-execute one OpenCL COP kernel on-GPU; enable
`options_iteration` when the kernel needs the current `@Iteration` value.

### Time Bindings

`@Time` is available only when **Include Time** is enabled. `@TimeInc` is
available only when **Include Timestep** is enabled; **Use Context's
Timestep** controls whether that value comes from the surrounding context.

## Simulations and Blocks

Copernicus simulations use a Block Begin and Block End pair to feed the block's
outputs back into its inputs on the next timeline step.

For a typical user-authored simulation:

1. Create the **Block** recipe, which places a Block Begin and Block End and
   sets the Begin node's **Block Path** to the End node.
2. Turn on **Simulate** on the Block End.
3. Add matching inputs and outputs to the Block Begin and Block End. Match each
   port's order, name, and data type.
4. Wire initial data into the Block Begin inputs.
5. Wire processing nodes from the Block Begin outputs to the corresponding
   Block End inputs. These nodes define one simulation step.
6. Advance or play the timeline to evaluate successive feedback steps.

Block ports carry typed COP data such as Mono, UV, RGB, RGBA, geometry, VDBs,
or cables. They are not scalar control parameters. Multiple independent state
layers can be fed back through separate matching ports.

Copernicus layers can also serve as general GPU data buffers rather than
displayable images. Texels may store fields, records, velocities, IDs, or
other structured state, with multiple layers carrying independent data
through the simulation block.

### Rasterizing Geometry Data

SOP Import brings geometry into Copernicus, where Rasterize Setup can unwrap
it into UV space and Rasterize Geometry can convert arbitrary numeric
attributes into layers. Preserving attributes such as original position and
normal allows UV-space effects to remain aware of geometry-space position,
orientation, and other SOP data. This provides a practical bridge between
geometry, image, UV, and world-space processing.

Keep operations that do not depend on previous simulation results outside the
block when possible. Bring external data into the block only when it must be
sampled during each step; return only state that must feed back.

Do not enable **Live Simulation** unless the user explicitly requests it. Live
Simulation runs independently of the timeline, is non-deterministic, and does
not use normal timeline caching.

Flow, Reaction-Diffusion, and Pyro Block recipes are specialized,
preconfigured solvers built on the same block mechanism. Their visible Begin
and End nodes are HDAs that contain much of the solver logic internally, so
they may be wired directly together rather than exposing a typical
user-authored processing network between them. Inspect their internal networks
and dedicated documentation before modifying their solver structure.

### COP HDA Packaging IO

Copernicus/COP `subnet` nodes are created with a canonical top-level
`inputs -> outputs` pair, which becomes the HDA boundary on conversion.

When packaging a COP chain into an HDA, wire the effect through those existing
nodes rather than creating a second top-level `input`/`output` pair.

## Common Patterns

### Atomic Accumulation

User-authored OpenCL COP kernels can use atomics when the target layer is bound
as writable/inout with `&`. Regular layer bindings do not expose raw storage;
use the generated `.data` pointer on an `&` binding:

Prefer integer atomics for counts. Feed `&counts int` from a fresh zero-filled,
32-bit ID Layer at the target resolution (not a Mono Constant), and consume the
generated `counts` output. Reset it for every accumulation pass; do not feed it
back as simulation state. Use `x + y * xres` for linear indexing.

```c
#bind layer src float
#bind layer &counts int

@KERNEL
{
    global int *data = @counts.data;
    atomic_inc(&data[0]);
}
```

For float accumulation, use a compare-and-swap loop because portable native
float `atomic_add` is not available:

```c
static void atomic_add_float_global(global float *addr, float val)
{
    volatile global unsigned int *uaddr = (volatile global unsigned int *)addr;
    unsigned int old = *uaddr;
    unsigned int assumed;
    do
    {
        assumed = old;
        float next = as_float(assumed) + val;
        old = atomic_cmpxchg(uaddr, assumed, as_uint(next));
    }
    while (old != assumed);
}

#bind layer src float
#bind layer &accum float

@KERNEL
{
    global float *data = @accum.data;
    atomic_add_float_global(&data[0], 1.0f);
}
```

Keep atomic branches isolated and validate/cook them before using them in a
solver. A bad atomic kernel may leave NVIDIA OpenCL reporting
`CL_OUT_OF_RESOURCES` / `clEnqueueWriteBuffer (-5)` until Houdini restarts.

### Neighborhood Sampling

Use a normal layer binding and integer indices for convolution, morphology, or local statistics:

```c
#bind layer src
#bind layer !&dst

@KERNEL
{
    float4 sum = 0.0f;
    for (int y = -1; y <= 1; y++)
    {
        for (int x = -1; x <= 1; x++)
        {
            sum += @src.bufferIndex(@ixy + (int2)(x, y));
        }
    }
    @dst.set(sum / 9.0f);
}
```

Border behavior follows the source layer's border mode. Explicitly clamp when the algorithm must not wrap, mirror, or use a constant border.

### Optional Layer Override

```c
#if @strength.bound
    float strength = @strength;
#else
    float strength = 1.0f;
#endif
```

### Geometry Attributes

```c
#bind point points name=P float3 port=geo
```

Use `@points.len` for the element count and `@points(i)` for indexed access. Avoid naming an attribute binding `P` when the global `@P` binding is active; use an alias such as `geoP`.

### Rank Selection

For small parallel sorts:

1. Identify the sortable span.
2. For each element, count elements with a lower sort key.
3. Use that rank as the destination index.
4. Write with `@name.setIndex(int2, value)`.

## OpenCL Language Gotchas

- `fract(x)` does not compile because OpenCL requires a second pointer argument. Use `x - floor(x)` when only the fractional part is needed.
- `abs()` is for integers. Use `fabs()` for floating-point scalars and vectors.
- Unsuffixed literals can compile with an explicit target type, but `f` suffixes remain a clear portable convention.
- `bufferIndex()` and `setIndex()` require `int2`; never pass `@P`.
- `sincos(angle, &cos_value)` can replace separate `sin` and `cos` calls.
- `select(a, b, condition)` can avoid simple divergent branches.

## Installed Headers

Inspect Houdini's installed OpenCL headers when built-in behavior is unclear:

- `houdini_install_path\houdini\ocl\include\imx.h`
- `houdini_install_path\houdini\ocl\include\imx_internal.h`
- `houdini_install_path\houdini\ocl\include\imx_filter.h`
- `houdini_install_path\houdini\ocl\include\imx_filter_internal.h`

Common imported headers include `postprocessing.h`, `mtlx_noise.h`, and `random.h`.

## Live Inspection

Find and inspect a native kernel:

```text
houdini-cli node find <node-path> --type opencl --max-depth 5
houdini-cli parm get <opencl-node-path>/kernelcode
```

After editing:

```text
houdini-cli opencl sync <node-path> --clear
houdini-cli opencl validate <node-path>
houdini-cli node errors <node-path>
```

For visual confirmation, set the display flag and capture the viewport:

```text
houdini-cli node flags set <node-path> --display true
houdini-cli session screenshot --index 0 --output <path.png>
```

## References

- [Kernel Reference Index](kernel_reference_index.md)
- [OpenCL for VEX Users](../help_prepared/vex/ocl.txt)
- [OpenCL COP](../help_prepared/nodes/cop/opencl.txt)
- [Copernicus Introduction](../help_prepared/copernicus/intro.txt)
