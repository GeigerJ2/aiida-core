---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
execution:
  timeout: 300
---

(tutorial:module6)=
# Module 6: Complex workflows

:::{note}
This module reuses the tutorial profile and the `python_code` object created in {ref}`Module 1 <tutorial:module1>`, and assumes you have read {ref}`Module 3 <tutorial:module3>` (`@task.graph()`, `Map`, `shelljob`).
If you are following along locally, run those first.
:::

## What you will learn

After this module, you will be able to:

- Decide a workflow's **shape at runtime** using `If` and `While` zone tasks, so steps run only when they should and loops iterate until convergence.
- Construct a workflow's structure from data that **was not known in advance**, using a calcfunction to turn coarse-sweep results into a refined parameter set.
- Pull these features together into an **adaptive sweep** that focuses computational effort where the physics is most interesting.

```{code-cell} ipython3
:tags: ["remove-cell"]

# Auto-generated tutorial profile for docs build.
# If running locally with your own profile (e.g. from ``verdi presto``),
# replace this cell with:
#
#     from aiida import load_profile
#     load_profile()

%load_ext aiida
%run -i include/setup_tutorial.py
```

## When fixed-shape workflows aren't enough

Module 3's `gray_scott_pipeline` and `gray_scott_sweep` had a **fixed shape**: the same three steps for every parameter set, the same map fan-out, the same reduction at the end.
That's the right shape when you already know what you want to compute.
Real research is rarely that tidy:

- An expensive diagnostic is only worth running on the runs where it would say something useful.
- A simulation has a free parameter (a time step, a tolerance, a grid size) that has to be *driven* until a quantity stabilises.
- The interesting parameter range only becomes clear *after* a first cheap scan.

WorkGraph supports all three through three small pieces of machinery, on top of what you already know:

- `If` and `While` are **zone tasks**, written as Python context managers in your graph definition; they select which tasks belong to a region of the graph that may run zero, one, or many times.
- The graph's `ctx` is a shared, mutable key-value store, the WorkGraph analogue of the WorkChain `ctx`. Writing into it from inside a `While` zone is what lets the loop iterate over evolving state.
- Any calcfunction whose output is a `dict` can be used to **build a parameter set for a downstream `Map`**, because calcfunctions are AiiDA processes whose outputs flow through normal socket connections.

:::{important}
The single mental shift this module is built on is this: **the workflow graph is data that you build**.
Once you accept that, control flow is just normal Python that *adds tasks* to the graph, gated on the outputs of *other* tasks.
`If`, `While`, and `Map` zones don't run Python branches; they declare regions of the graph whose execution is decided at runtime by AiiDA from the values of the sockets you wired in.
:::

## Conditional analysis with `If`

A simple example: most useful diagnostics are not free.
Running an FFT on the V-field to estimate the dominant pattern wavelength only makes sense for runs that *show* a pattern; spending the same cost on a flat run wastes time and clutters the provenance with meaningless numbers.

We have everything needed from earlier modules:

- `variance_V` is computed cheaply by `parse_output` (Module 2). It is a good `is there a pattern at all?` predicate.
- The full V-field is in `results.npz` (Module 2). The expensive analysis reads it.

`include/tasks.py` exposes a small calcfunction that wraps the analysis:

```{code-cell} ipython3
from include.tasks import fft_peak_wavelength
help(fft_peak_wavelength)
```

The recipe is the gating itself.
We extend the Module 3 pipeline with one `If` zone: the FFT task is only added to the *running* graph when the cheap predicate exceeds a threshold.

```{code-cell} ipython3
from typing import Annotated

from aiida import orm
from aiida_workgraph import If, task, shelljob

from include.constants import BASE_PARAMS
from include.tasks import prepare_input, parse_output


@task.graph()
def pipeline_with_optional_fft(
    parameters: orm.Dict,
    command: orm.AbstractCode,
    variance_threshold: float,
):
    """Run gsrd, parse it, and run an FFT analysis *only if* the run looks interesting."""
    prepared = task(prepare_input)(parameters=parameters)
    simulation = shelljob(
        command=command,
        arguments=['{input}'],
        nodes={'input': prepared.result},
        outputs=['results.npz'],
    )
    parsed = task(parse_output)(stdout=simulation.stdout)

    with If(parsed.variance_V > variance_threshold):
        task(fft_peak_wavelength)(results_npz=simulation.results_npz)
```

:::{note}
Two details worth noticing:

- **`parsed.variance_V > variance_threshold` is not a Python boolean.** It is a comparison between an output socket and a value, which WorkGraph compiles into a tiny operator task whose output is itself a socket. That socket is what `If(...)` reads to decide whether to enter the zone at runtime.
- **The body of the `with If(...)`** is not skipped at definition time. Every task inside it is registered into the graph; it is the *execution* of those tasks that the zone gates. This is the same dual-life idea as Module 3's `Map`: build now, decide later.
:::

To see the difference, build the same workflow twice with the same threshold but different `F`.
At `F = 0.04` the pattern is strong (`variance(V) ≈ 1e-2`), so the FFT fires.
At `F = 0.060` the pattern is much weaker (`variance(V) ≈ 5e-4`), so the FFT is skipped entirely.

```{code-cell} ipython3
wg_strong = pipeline_with_optional_fft.build(
    parameters=orm.Dict({**BASE_PARAMS, 'F': 0.040}),
    command=gsrd_code,
    variance_threshold=0.005,
)
wg_strong.run()
wg_weak = pipeline_with_optional_fft.build(
    parameters=orm.Dict({**BASE_PARAMS, 'F': 0.060}),
    command=gsrd_code,
    variance_threshold=0.005,
)
wg_weak.run()
```

```{code-cell} ipython3
def labels_in(process):
    return sorted({c.process_label for c in process.called_descendants})


print(f'F = 0.040 ({len(wg_strong.process.called_descendants)} child processes): {labels_in(wg_strong.process)}')
print(f'F = 0.060 ({len(wg_weak.process.called_descendants)} child processes): {labels_in(wg_weak.process)}')
```

The first run records a `fft_peak_wavelength` process; the second doesn't. Both runs took the same code through the same `@task.graph()` definition; the **shape** of what AiiDA ran (and recorded) is different.

::::{dropdown} A different shape: skip an expensive *rerun*, not an expensive *analysis*
:icon: code

The same `If` machinery covers the related case where the expensive thing isn't a post-processing task but a *second simulation* (e.g., a higher-resolution rerun for runs that look pattern-forming).
The structure is identical; only the body of the `If` changes:

```python
with If(parsed.variance_V > variance_threshold):
    hires = shelljob(
        command=command,
        arguments=['{input}'],
        nodes={'input': prepare_input_task(
            parameters={**parameters.get_dict(), 'grid_size': 128}
        ).result},
        outputs=['results.npz'],
    )
```

The takeaway is that an `If` zone is just "a region of the graph that runs only when this socket is truthy." What you put inside it is up to you.
::::

## Iterative simulation with `While`

The next adaptive pattern is iteration.
The Gray-Scott simulation runs for a fixed `n_steps`, and we don't always know in advance how many time steps the pattern needs to settle.
A clean way to handle that is to keep extending the simulation, in 1000-step chunks, until `variance(V)` reaches the saturation level the parameter region produces.

That kind of feedback loop needs three things WorkGraph exposes through `wg.ctx`:

- A place to **initialise** the loop state (`wg.ctx = {...}` before the zone).
- A condition that **reads** ctx and is recomputed every iteration (the `While(...)` argument).
- Tasks inside the zone that **write back** into ctx, so the next iteration sees updated values.

To express the loop directly we drop into WorkGraph's imperative form (`with WorkGraph() as wg:`).
This is the same WorkGraph object you would get from `@task.graph().build(...)`; the imperative form just gives us a name (`wg`) we can attach `wg.ctx` to.

```{code-cell} ipython3
from aiida_workgraph import While, WorkGraph
from include.tasks import bump_n_steps

prepare_input_task = task(prepare_input)
parse_output_task = task(parse_output)
bump_n_steps_task = task(bump_n_steps)


@task()
def reached_plateau(variance: float, target: float) -> bool:
    """Return True once variance(V) reaches the saturation target."""
    return float(variance) >= float(target)
```

Each iteration runs gsrd at the current `n_steps`, measures `variance(V)`, and either stops (target reached) or bumps `n_steps` and goes again.

```{code-cell} ipython3
initial_params = orm.Dict({**BASE_PARAMS, 'F': 0.040, 'n_steps': 1000})

with WorkGraph('extend_to_plateau') as wg_loop:
    wg_loop.ctx = {
        'parameters': initial_params,
        'done': orm.Bool(False),
    }
    with While(wg_loop.ctx.done == False, max_iterations=8):  # noqa: E712
        prepared = prepare_input_task(parameters=wg_loop.ctx.parameters)
        simulation = shelljob(
            command=gsrd_code,
            arguments=['{input}'],
            nodes={'input': prepared.result},
            outputs=['results.npz'],
        )
        parsed = parse_output_task(stdout=simulation.stdout)
        done = reached_plateau(variance=parsed.variance_V, target=0.012)
        wg_loop.ctx.parameters = bump_n_steps_task(
            parameters=wg_loop.ctx.parameters, increment=orm.Int(1000)
        ).result
        wg_loop.ctx.done = done.result

wg_loop.run()
print(f'\nFinal state: {wg_loop.state}')
```

:::{important}
**Reassigning a Python variable inside a `While` body does *not* create a feedback edge.**
Writing `prepared = prepare_input_task(...)` rebinds the *Python* name but does not tell WorkGraph that the next iteration's `parameters` should come from somewhere different.
For state that has to flow from one iteration to the next, **write it into `wg.ctx`** and read it back from `wg.ctx` at the top of the body.
That is what the two `wg_loop.ctx.<name>` assignments above are for: `parameters` carries the growing `n_steps` between iterations, and `done` carries the stopping signal.
:::

The provenance shows one `ShellJob` (and the surrounding calcfunctions) per iteration:

```{code-cell} ipython3
:tags: ["hide-input"]
:mystnb:
:    code_prompt_show: 'Show inspection code (recover per-iteration n_steps and variance)'

iterations = []
for parse_node in wg_loop.process.called_descendants:
    if parse_node.process_label != 'parse_output':
        continue
    sim_stdout = parse_node.inputs.stdout
    sim_node = sim_stdout.creator
    n_steps = sim_node.inputs.nodes.input.creator.inputs.parameters.get_dict()['n_steps']
    variance = float(parse_node.outputs.variance_V.value)
    iterations.append((sim_node.ctime, n_steps, variance))

iterations.sort()
print(f'{len(iterations)} gsrd runs nested under the workflow:\n')
for n, (_, n_steps, variance) in enumerate(iterations, start=1):
    print(f'  iter {n}: n_steps = {n_steps:5d}  variance(V) = {variance:.4e}')
```

:::{tip}
The condition only references ctx values that the **current** iteration is responsible for setting (`done`).
This is the cleanest shape for a `While` loop in WorkGraph: each iteration *only* writes the ctx keys it owns, and the condition reads keys whose value is fully determined by a single task in the current iteration.
A loop whose condition compares "this iteration vs. last iteration" needs the previous value to *outlive* the current iteration's writes, which requires more care (you have to route the previous value through the comparing task explicitly so the engine sees the read-before-write dependency).
::: 

::::{dropdown} Why we don't loop over `dt` here
:icon: question

A natural alternative is **time-step convergence**: halve `dt` and double `n_steps` (keeping the simulated time `dt * n_steps` constant) until `variance(V)` stops changing.
That probes whether the integrator itself is converged, independent of how long you run the simulation.

For the tutorial's parameter regime (`F = 0.04`, `dt = 1.0`, etc.) the integrator is already converged at `dt = 1.0` to four significant figures, so a `While` loop on `dt` would terminate after a single iteration.
That makes for poor pedagogy: the loop reads as iterative but the data say it never had to be.
We chose `n_steps` (i.e., simulated time) because it *does* drift across iterations at our parameters, so the loop does real work and exits on a real saturation condition.

If your code has a tighter stability margin or your parameters live near the CFL limit, the same `While`+`ctx` skeleton applies to `dt` unchanged; the only thing that moves is what `bump_n_steps` becomes.
::::

## Composing graphs of graphs

Everything we have written so far is just a graph: `pipeline_with_optional_fft` is a graph; the `wg_loop` we just ran is a graph; Module 3's `gray_scott_pipeline` was a graph.
A `@task.graph()` can be added as a single task inside any other graph, which is what keeps each level small and readable.

The mechanic is the same one Module 3 used to put `gray_scott_pipeline` inside `gray_scott_sweep`'s `Map`: call the inner graph like a function from the outer graph's body, and AiiDA wires the inputs/outputs through.
Here we reuse `pipeline_with_optional_fft` inside a `Map` zone so the `If`-gated FFT now decides itself, per iteration:

```{code-cell} ipython3
:tags: ["hide-output"]

from aiida_workgraph import Map, dynamic

from include.constants import F_VALUES


@task.graph()
def conditional_sweep(
    param_sweep: Annotated[dict, dynamic(dict)],
    command: orm.AbstractCode,
    variance_threshold: float,
):
    """A coarse F-sweep where each iteration decides for itself whether to run the FFT."""
    with Map(param_sweep) as m:
        pipeline_with_optional_fft(
            parameters=m.item.value,
            command=command,
            variance_threshold=variance_threshold,
        )


param_sweep = {
    f'F_{f:.3f}'.replace('.', '_'): {**BASE_PARAMS, 'F': f}
    for f in F_VALUES
}
wg_cond = conditional_sweep.build(
    param_sweep=param_sweep,
    command=gsrd_code,
    variance_threshold=0.005,
)
wg_cond.run()
```

The provenance now records the FFT only for the runs that earned it.
We can see this by counting how many `fft_peak_wavelength` calcfunctions ran in total and comparing to the number of sweep points:

```{code-cell} ipython3
fft_runs = sum(
    1 for c in wg_cond.process.called_descendants
    if c.process_label == 'fft_peak_wavelength'
)
print(f'FFT ran for {fft_runs} of {len(param_sweep)} sweep points '
      f'(threshold variance(V) > 0.005).')
```

This is what `If` inside `Map` buys: the *shape* of each iteration is decided by that iteration's data, not by something we knew when we wrote the graph.

## Putting it together: an adaptive sweep

The final pattern combines the dynamic-shape idea with one more move: building *part of the graph from the output of an earlier part of the same graph*.
Concretely, we want a coarse `F`-sweep to *decide* where a refined sweep should land, then refine there.
The interesting parameter values do not exist when the workflow starts; they are computed midway through.

The recipe has three parts:

1. **Coarse sweep**: run gsrd over a sparse grid of `F` values to locate the transition.
2. **Identify**: a task (`identify_transition_region`) consumes the coarse `{F: variance}` map and returns a refined parameter sweep clustered around the steepest variance jump.
3. **Refined sweep + analysis**: a second `Map` runs gsrd plus an FFT on each refined point.

The trick that makes step 3 depend on step 2 is the `Map` source: it is a *socket* (`refined.result`), not a Python dict, so AiiDA only enumerates the iteration keys once the coarse sweep has finished.

First, a tiny sub-graph that bundles the gsrd run plus its parser into one reusable step.
We will use it twice below: once for the coarse sweep (variance only) and once for the refined sweep (variance plus FFT on the same simulation's `results.npz`).

```{code-cell} ipython3
from aiida_workgraph import namespace

from include.tasks import identify_transition_region

fft_peak_wavelength_task = task(fft_peak_wavelength)


@task.graph()
def simulate(
    parameters: orm.Dict,
    command: orm.AbstractCode,
) -> namespace(variance_V=float, results_npz=orm.SinglefileData):
    """Run gsrd once and parse it. Exposes variance_V (scalar) and results_npz (file)."""
    prepared = prepare_input_task(parameters=parameters)
    sim = shelljob(
        command=command,
        arguments=['{input}'],
        nodes={'input': prepared.result},
        outputs=['results.npz'],
    )
    parsed = parse_output_task(stdout=sim.stdout)
    return {'variance_V': parsed.variance_V, 'results_npz': sim.results_npz}
```

Now the adaptive sweep itself.
It is one `@task.graph()` that contains two `Map` zones; the second one's source comes from a task that consumes the first one's output.

```{code-cell} ipython3
@task.graph()
def adaptive_sweep(
    coarse_sweep: Annotated[dict, dynamic(dict)],
    base_parameters: orm.Dict,
    command: orm.AbstractCode,
    n_refined: orm.Int,
) -> namespace(
    coarse_variances=dynamic(float),
    refined_variances=dynamic(float),
    refined_wavelengths=dynamic(float),
):
    """Coarse F-sweep -> locate transition -> refined sweep with FFT on each point."""
    # 1. Coarse sweep: only the variance is needed to locate the transition.
    with Map(coarse_sweep) as coarse:
        run = simulate(parameters=coarse.item.value, command=command)
        coarse.gather({'variance_V': run.variance_V})

    # 2. Identify: build the refined sweep dict from the coarse variances.
    refined = identify_transition_region(
        variances=coarse.outputs.variance_V,
        base_parameters=base_parameters,
        n_refined=n_refined,
    )

    # 3. Refined sweep: the Map source is the *socket* refined.result, not a static dict.
    with Map(refined.result) as fine:
        fine_run = simulate(parameters=fine.item.value, command=command)
        wavelength = fft_peak_wavelength_task(results_npz=fine_run.results_npz)
        fine.gather({
            'variance_V': fine_run.variance_V,
            'wavelength': wavelength.result,
        })

    return {
        'coarse_variances': coarse.outputs.variance_V,
        'refined_variances': fine.outputs.variance_V,
        'refined_wavelengths': fine.outputs.wavelength,
    }
```

```{code-cell} ipython3
:tags: ["hide-output"]

# A slightly longer simulation than the M2/M3 default so the FFT analysis
# has well-developed patterns to measure.
adaptive_base = {**BASE_PARAMS, 'n_steps': 8000}

coarse_sweep_input = {
    f'F_{f:.3f}'.replace('.', '_'): {**adaptive_base, 'F': f}
    for f in F_VALUES
}

wg_adaptive = adaptive_sweep.build(
    coarse_sweep=coarse_sweep_input,
    base_parameters=orm.Dict(adaptive_base),
    command=gsrd_code,
    n_refined=orm.Int(5),
)
wg_adaptive.run()
```

The refined sweep is clustered where the coarse sweep showed the steepest change in variance. Inspect both:

```{code-cell} ipython3
:tags: ["hide-input"]
:mystnb:
:    code_prompt_show: 'Show plotting code: coarse + refined transition curves'

import matplotlib.pyplot as plt


def _key_to_f(key: str) -> float:
    parts = key.split('_')
    return float(f'{parts[1]}.{parts[2]}')


coarse_var = {_key_to_f(k): float(v) for k, v in wg_adaptive.outputs.coarse_variances._value.items()}
refined_var = {_key_to_f(k): float(v) for k, v in wg_adaptive.outputs.refined_variances._value.items()}

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(sorted(coarse_var), [coarse_var[f] for f in sorted(coarse_var)],
        'o-', color='tab:blue', label='coarse sweep')
ax.plot(sorted(refined_var), [refined_var[f] for f in sorted(refined_var)],
        's-', color='tab:orange', label='refined sweep')
ax.set_xlabel('Feed rate F')
ax.set_ylabel('variance(V)')
ax.set_yscale('log')
ax.set_title('Adaptive Gray-Scott sweep')
ax.legend()
ax.grid(True, alpha=0.3)
fig.tight_layout()
plt.show()
```

The wavelength estimate from the FFT is in there too, one per refined point:

```{code-cell} ipython3
wavelengths = wg_adaptive.outputs.refined_wavelengths._value
for key in sorted(wavelengths):
    print(f'  F = {_key_to_f(key):.4f}  ->  wavelength = {float(wavelengths[key]):.2f} cells')
```

What AiiDA recorded is one workflow node with the whole story attached: the coarse `Map`, the `identify_transition_region` step that bridged the two, the refined `Map`, and the per-point FFT analysis.
None of the refined parameter values existed before the workflow ran.

## Next steps

You can now build workflows whose shape depends on intermediate data, not just on what you knew when you wrote the script.
The remaining piece, recovering from failures (exit codes, retries, parameter adjustments), is the topic of {ref}`Module 7 <tutorial:module7>`.
Error handlers are themselves another control-flow feature of WorkGraph: a way to extend the graph dynamically when a task fails, rather than when a predicate succeeds.

## Further reading

- WorkGraph concepts and process abstractions: {ref}`topics:workflows`, {ref}`topics:workflows:concepts`
- Process states and exit codes (background for Module 7): {ref}`topics:processes:concepts`, {ref}`topics:processes:concepts:exit_codes`
- WorkGraph `If` / `While` / `Map` zone tasks and the graph context: [aiida-workgraph documentation](https://aiida-workgraph.readthedocs.io)
- Building data products from provenance after the fact (instead of inside the workflow): {ref}`Module 5 <tutorial:module5>`
