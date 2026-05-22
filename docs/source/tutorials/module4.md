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
  timeout: 240
---

(tutorial:module4)=
# Module 4: Remote submission

<!-- TODO: re-enable once the md->ipynb conversion script is verified
:::{tip}
This tutorial can be downloaded and run as a Jupyter notebook: {nb-download}`module4.ipynb` {octicon}`download`
:::
-->

:::{note}
This module reuses the tutorial profile created in {ref}`Module 1 <tutorial:module1>`.
If you are following along locally, run that module first. To use your own profile instead, replace the setup cell at the top of the downloaded notebook with:

```python
from aiida import load_profile

load_profile()
```
:::

## What you will learn

After this module, you will be able to:

- Understand where a calculation runs: the Computer, how AiiDA connects to it, and how its jobs are queued
- Configure a remote HPC cluster and register a code that lives on it
- Send a calculation to the cluster instead of your own machine

```{code-cell} ipython3
:tags: ["remove-cell"]

# Tutorial profile setup (shared across modules).
%load_ext aiida
%run -i include/setup_tutorial.py
```

```{code-cell} ipython3
:tags: ["remove-cell"]

# SSH plumbing for the SLURM container (key + ~/.ssh/config).
# If running locally, you would configure SSH to your own cluster instead.
%run -i include/setup_slurm.py
```

## Where calculations run

Every calculation so far has run on `localhost` &mdash; your own machine.
Real research rarely does: simulations run on **HPC clusters**, shared machines you reach over the network, where jobs wait in a scheduler queue until resources free up.

You do **not** have to rewrite your workflow for that.
In {ref}`Module 1 <tutorial:module1>` we met the two objects AiiDA uses to abstract *where* work happens:

- A **{ref}`Computer <how-to:run-codes:computer>`** describes *where* to run. It bundles the hostname, a **transport** (how AiiDA connects and moves files &mdash; `core.local` for your machine, `core.ssh_async` for a remote one) and a **scheduler** (how the machine runs jobs &mdash; `core.direct` runs them immediately, `core.slurm` / `core.pbspro` queue them through a batch system).
- A **{ref}`Code <how-to:run-codes:code>`** describes *what* runs there: the executable's path on that computer.

The tutorial's `localhost` is just the simplest case: local transport, direct scheduler.
Here is what it looks like from the inside:

```{code-cell} ipython3
%verdi computer show localhost
```

The `transport_type` is `core.local` (copy files on the same filesystem) and the `scheduler_type` is `core.direct` (run immediately, no queue).
A remote HPC cluster differs in exactly these two fields: `core.ssh_async` for the transport, and `core.slurm` (or `core.pbspro`, `core.sge`, etc.) for the scheduler.
The majority of this module is setting those two up.

## Registering a remote computer

Registering a remote computer is a one-time, three-step process: **setup** (describe the machine), **configure** (provide connection credentials), and **test** (verify everything works).

:::{note}
This tutorial uses a SLURM container reachable over SSH so that every cell executes automatically during the docs build.
A hidden cell handles the SSH plumbing (key and `~/.ssh/config`); all `verdi` commands below run live.
In practice, you would register whichever HPC cluster you actually have access to.
:::

### Setup

`verdi computer setup` registers the machine in AiiDA's database:

```{code-cell} ipython3
:tags: ["remove-cell"]

# Clean up any slurm-ssh computer left over from a previous build so the
# live `verdi computer setup` cell is idempotent across rebuilds.
from contextlib import suppress

from aiida.common.exceptions import NotExistent
from aiida.orm import AuthInfo, Computer, Node, QueryBuilder, User, load_computer
from aiida.tools import delete_nodes

with suppress(NotExistent):
    _old = load_computer('slurm-ssh')
    _node_pks = (
        QueryBuilder()
        .append(Computer, filters={'id': _old.pk}, tag='comp')
        .append(Node, with_computer='comp', project='id')
        .all(flat=True)
    )
    if _node_pks:
        delete_nodes(_node_pks, dry_run=False)
    with suppress(NotExistent):
        _ai = _old.get_authinfo(User.collection.get_default())
        AuthInfo.collection.delete(_ai.pk)
    Computer.collection.delete(_old.pk)
```

```{code-cell} ipython3
%verdi computer setup \
    --label slurm-ssh \
    --hostname slurm-ssh \
    --transport core.ssh_async \
    --scheduler core.slurm \
    --work-dir /home/{username}/workdir \
    --mpiprocs-per-machine 1 \
    --non-interactive
```

The key flags:

- `--transport core.ssh_async`: AiiDA connects and moves files over SSH.
- `--scheduler core.slurm`: jobs go through SLURM (`sbatch`, `squeue`, `scancel`). Other options include `core.pbspro`, `core.sge`, `core.lsf`, and `core.direct` (no scheduler, run immediately).
- `--work-dir`: where AiiDA creates per-calculation working directories on the remote machine. `{username}` is expanded at runtime.

::::{tip}
On a real HPC cluster the hostname would be the cluster's login node (e.g. `daint.alps.cscs.ch`), and the work directory typically a scratch filesystem.
Instead of typing flags, you can pass a YAML file:

```console
$ verdi computer setup --config computer.yaml
```

:::{dropdown} Example `computer.yaml` for a SLURM cluster
```yaml
---
label: "daint"
hostname: "daint.alps.cscs.ch"
transport: "core.ssh_async"
scheduler: "core.slurm"
work_dir: "/scratch/{username}/aiida"
mpirun_command: "srun -n {tot_num_mpiprocs}"
mpiprocs_per_machine: 36
prepend_text: |
    module load cray-python
```
:::

The [AiiDA resource registry](https://github.com/aiidateam/aiida-resource-registry) maintains ready-made YAML configs for common HPC centres.
Download the one for your cluster and pass it directly.
If your cluster is not listed yet, contributions are welcome: open a PR to add your YAML files so others can benefit too.
::::

Everything `verdi` can do is also available through the Python API.
Look for the dropdowns below each section to see the equivalent Python code.

:::{dropdown} Python API: computer setup
```python
from aiida.orm import Computer

computer = Computer(
    label='slurm-ssh',
    hostname='slurm-ssh',
    transport_type='core.ssh_async',
    scheduler_type='core.slurm',
    workdir='/home/{username}/workdir',
).store()
```
:::

### Configure

`verdi computer configure` provides the connection details for the chosen transport.

For `core.ssh_async`, AiiDA reads your `~/.ssh/config`, so as long as `ssh <hostname>` works from your terminal, the configure step needs no extra credentials:

```{code-cell} ipython3
%verdi computer configure core.ssh_async slurm-ssh --backend openssh --non-interactive
```

:::{tip}
`core.ssh_async` supports two SSH backends: `asyncssh` (the default, pure-Python) and `openssh` (shells out to the system's `ssh` binary).
We use `--backend openssh` here because this tutorial's SLURM container runs an older OpenSSH server.
On modern HPC clusters the default `asyncssh` backend works well; you can omit the `--backend` flag entirely.
:::

:::{warning}
The older `core.ssh` transport is **deprecated and will be removed in v3.0**.
It requires configuring username, port, key path, and other SSH parameters through `verdi` prompts.
`core.ssh_async` replaces it: it is significantly faster and delegates connection settings to your `~/.ssh/config`, which is simpler and more consistent with how you already manage SSH connections.
:::

:::{dropdown} Python API: computer configure
```python
computer.configure()
```

`configure()` accepts the same keyword arguments as the `verdi computer configure` prompts (e.g. `host='slurm-ssh'`, `backend='openssh'`).
:::

```{code-cell} ipython3
:tags: ["remove-cell"]

# Speed up job polling for the tutorial (default interval is too slow).
from aiida.orm import load_computer

slurm_computer = load_computer('slurm-ssh')
slurm_computer.set_minimum_job_poll_interval(1)
```

Let's inspect the computer we just registered:

```{code-cell} ipython3
%verdi computer show slurm-ssh
```

### Test

`verdi computer test` runs a series of connection and scheduler checks.
All checks must pass before the computer is usable:

```{code-cell} ipython3
%verdi computer test slurm-ssh
```

You now have two computers in your profile:

```{code-cell} ipython3
%verdi computer list
```

## Registering a remote code

With the computer in place, register the executable that lives on the cluster.
AiiDA supports three code types:

- **{ref}`InstalledCode <topics:data_types:core:code:installed>`** &mdash; the executable is already present on the computer. This is the common case: your simulation code is installed on the cluster.
- **{ref}`PortableCode <topics:data_types:core:code:portable>`** &mdash; AiiDA stores the code in its repository and uploads it to the computer at run time. Useful for small scripts or tools you want to keep versioned in AiiDA.
- **{ref}`ContainerizedCode <topics:data_types:core:code:containerized>`** &mdash; the executable runs inside a container (Singularity, Docker) on the computer.

For an `InstalledCode`, you specify the path to the executable on the remote machine.
Let's register `gsrd` on the tutorial's SLURM container:

```{code-cell} ipython3
%verdi code create core.code.installed \
    --label gsrd \
    --computer slurm-ssh \
    --filepath-executable /opt/gsrd/bin/gsrd \
    --default-calc-job-plugin core.shell \
    --non-interactive
```

The code is now addressable as `gsrd@slurm-ssh`, just like the local code is `gsrd@localhost`.

:::{tip}
On a real cluster, the executable is usually activated through a module system.
The `--prepend-text` flag adds lines to the job script *before* the executable, typically `module load` commands:

```console
$ verdi code create core.code.installed \
    --label gsrd \
    --computer daint \
    --filepath-executable /apps/gsrd/bin/gsrd \
    --default-calc-job-plugin core.shell \
    --prepend-text 'module load gsrd/1.0'
```

This is the single most common customization for HPC codes: the executable exists, but the environment must be set up first.
:::

:::{dropdown} Python API: code registration
```python
from aiida.orm import InstalledCode

code = InstalledCode(
    label='gsrd',
    computer=computer,
    filepath_executable='/opt/gsrd/bin/gsrd',
    default_calc_job_plugin='core.shell',
).store()
```
:::

Here are all codes registered in this profile:

```{code-cell} ipython3
%verdi code list -A
```


## Running on the cluster

Here is the payoff.
The `launch_shell_job` call from {ref}`Module 1 <tutorial:module1>` does not change at all &mdash; you swap the Code object, and the same calculation runs on the cluster:

```{code-cell} ipython3
from pathlib import Path

from aiida.orm import load_code
from aiida_shell import launch_shell_job

input_path = Path('include/input.yaml').resolve()

results, node = launch_shell_job(
    load_code('gsrd@slurm-ssh'),
    arguments='{input}',
    nodes={'input': input_path},
    outputs=['results.npz'],
)

print(f"Process PK:  {node.pk}")
print(f"Computer:    {node.computer.label}")
print(f"Exit status: {node.exit_status}")
```

AiiDA handled everything: it opened the SSH connection, uploaded the inputs, submitted the job to the SLURM scheduler, polled until it finished, and retrieved the outputs.

:::{note}
We used `launch_shell_job(...)`, which blocks until the job finishes.
For real work, you would `submit()` the calculation (or a workflow wrapping it) to the AiiDA daemon, as shown in {ref}`Module 3 <tutorial:module3>`, and let it run in the background.
While a job sits in the cluster queue, it shows up as `Waiting` in `verdi process list`.
:::

Let's verify the outputs are there, just like in Module 1:

```{code-cell} ipython3
import io
import re

import numpy as np

with node.outputs.results_npz.open(mode='rb') as fh:
    arrays = np.load(io.BytesIO(fh.read()))
    v_field = arrays['V_final']

stdout_text = node.outputs.stdout.get_content()
var_v = float(re.search(r'Variance of V field\s*:\s*([\d.eE+-]+)', stdout_text).group(1))
mean_v = float(re.search(r'Mean\s+of V field\s*=\s*([\d.eE+-]+)', stdout_text).group(1))

print(f"V field shape: {v_field.shape}")
print(f"variance(V) = {var_v:.4e}")
print(f"mean(V)     = {mean_v:.4e}")
```

Same numbers, same provenance &mdash; the only difference is where the computation ran.

## Inspecting remote calculations

Every CalcJob exposes a `remote_folder` output, a {ref}`RemoteData <topics:data_types:core:remote>` node pointing at the working directory on the computer where it ran:

```{code-cell} ipython3
print(f"Remote working directory: {node.outputs.remote_folder.get_remote_path()}")
```

Two `verdi` commands make remote results tangible:

- **`verdi calcjob gotocomputer <PK>`** opens an SSH session and drops you straight into that working directory on the cluster &mdash; invaluable for inspecting a job after it finished or failed.
- **`verdi process dump <PK>`** (from {ref}`Module 1 <tutorial:module1>`) pulls the full inputs/outputs/logs tree to your local machine as readable files.

```{code-cell} ipython3
%verdi process show {node.pk}
```

The `Computer` column now reads `slurm-ssh` instead of `localhost`.
Everything else &mdash; the input/output links, the exit status, the `verdi` commands you use to inspect it &mdash; is identical.

## Next steps

You can now run calculations on remote HPC clusters with full provenance.
The remaining modules each pick up an independent thread and can be tackled in any order:

- {ref}`Module 5 <tutorial:module5>` &mdash; querying the database with the `QueryBuilder`
- {ref}`Module 6 <tutorial:module6>` &mdash; more advanced workflow patterns (conditionals, dynamic graphs, sub-workflow composition)
- {ref}`Module 7 <tutorial:module7>` &mdash; handling failures and recovering from them

## Further reading

- Transports (how AiiDA connects to computers): {ref}`topics:transport`
- Schedulers (batch systems that queue jobs): {ref}`topics:schedulers`
- Setting up and configuring computers: {ref}`how-to:run-codes:computer:setup`, {ref}`how-to:run-codes:computer:configuration`
- Code types (InstalledCode, PortableCode, ContainerizedCode): {ref}`topics:data_types:core:code`
- The AiiDA resource registry (pre-built computer/code configs): [github.com/aiidateam/aiida-resource-registry](https://github.com/aiidateam/aiida-resource-registry)
- `verdi calcjob gotocomputer` and other practical tips: {ref}`how-to:real-world-tricks`
