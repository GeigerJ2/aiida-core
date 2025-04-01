# Data mirroring in AiiDA

The simplest way to mirror your data out of AiiDA's internal database and file repository is through the CLI using the
`verdi [process|group|profile] mirror` endpoints.
By default, files will be mirrored to disk in the current working directory (CWD) and in `incremental` mirroring mode.
This means that, as you run your simulations through AiiDA and you keep executing the command, relevant files of
those new simulations will gradually be written to the directory.
Instead, if the command is run with the `-o/--overwrite` option, the output directory will be cleaned, and re-created from
scratch with the data available in the specified entity, be that an individual simulation, a group, or the whole AiiDA
profile.

The command was intended to further bridge the gap between research conducted with AiiDA and research data produced by
AiiDA with other scientists not familiar with AiiDA.
Some possible use cases that were considered while developing the feature are:
1. Zipping the resulting `mirror` directory of a data collection and sharing it with collaborators unfamiliar with AiiDA
   such that it can be explored by others, or
1. Periodically running the command (e.g., via `cron`) to reflect changes while working on a project, such that they can be analyzed.

## CLI options

All 3 commands provide various customization options to fine-tune their behavior. They are outlined below:

<details>
<summary><code>verdi process mirror -h</code></summary>

```
Options:
  -p, --path PATH                 Base path for mirror operations that write to disk.
  -o, --overwrite                 Overwrite file/directory when writing to
                                  disk.
  --include-inputs / --exclude-inputs
                                  Include linked input nodes of
                                  `CalculationNode`(s).  [default: include-
                                  inputs]
  --include-outputs / --exclude-outputs
                                  Include linked output nodes of
                                  `CalculationNode`(s).  [default: exclude-
                                  outputs]
  --include-attributes / --exclude-attributes
                                  Include attributes in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  attributes]
  --include-extras / --exclude-extras
                                  Include extras in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  extras]
  -f, --flat                      Mirror files in a flat directory for every
                                  step of a workflow.
  --mirror-unsealed / --no-mirror-unsealed
                                  Also allow the mirroring of unsealed process
                                  nodes.  [default: no-mirror-unsealed]
  -v, --verbosity [notset|debug|info|report|warning|error|critical]
                                  Set the verbosity of the output.
  -h, --help                      Show this message and exit.
```
</details>

<details>
<summary><code>verdi group mirror -h</code></summary>

```
Options:
  -p, --path PATH                 Base path for mirror operations that write
                                  to disk.
  -o, --overwrite                 Overwrite file/directory when writing to
                                  disk.
  --filter-by-last-mirror-time / --no-filter-by-last-mirror-time
                                  Only select nodes with an `mtime` after the
                                  last mirror time.  [default: filter-by-last-
                                  mirror-time]
  --mirror-processes / --no-mirror-processes
                                  Mirror process data.  [default: mirror-
                                  processes]
  --mirror-data / --no-mirror-data
                                  Mirror data nodes.  [default: no-mirror-data]
  --delete-missing / --no-delete-missing
                                  If a previously mirrored node is deleted
                                  from AiiDA's DB, also delete the
                                  corresponding mirror directory.  [default:
                                  no-delete-missing]
  --only-top-level-calcs / --no-only-top-level-calcs
                                  Mirror calculations in their own dedicated
                                  directories, not just as part of the
                                  mirrored workflow.  [default: only-top-
                                  level-calcs]
  --only-top-level-workflows / --no-only-top-level-workflows
                                  If a top-level workflow calls sub-workflows,
                                  create a designated directory only for the
                                  top-level workflow.  [default: only-top-
  --symlink-calcs / --no-symlink-calcs
                                  Symlink workflow sub-calculations to their own dedicated directories.  [default: no-symlink-
                                  calcs]
  --include-inputs / --exclude-inputs
                                  Include linked input nodes of
                                  `CalculationNode`(s).  [default: include-
                                  inputs]
  --include-outputs / --exclude-outputs
                                  Include linked output nodes of
                                  `CalculationNode`(s).  [default: exclude-
                                  outputs]
  --include-attributes / --exclude-attributes
                                  Include attributes in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  attributes]
  --include-extras / --exclude-extras
                                  Include extras in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  extras]
  -f, --flat                      Mirror files in a flat directory for every
                                  step of a workflow.
  -v, --verbosity [notset|debug|info|report|warning|error|critical]
                                  Set the verbosity of the output.
  -h, --help                      Show this message and exit.
```

</details>

As you can see, the `verdi group mirror` command exposes various options to specify the behavior of the mirroring of the selected group which influence the resulting directory structure.
These options are `filter-by-last-mirror-time`, `mirror-processes`, `mirror-data`, `delete-missing`, `only-top-level-calcs`,
`only-top-level-workflows`, and `symlink-calcs`,
In addition, the same options as for the `verdi process mirror` command are available. This is
because groups likely contain processes, and so the behavior of mirroring individual processes must be
controllable when mirroring the content of a group.

In accordance, the `verdi profile mirror` command exposes all options of `verdi process mirror` and `verdi group
mirror`, as well as additional options that can be seen below:

<details>
<summary><code>verdi profile mirror -h</code></summary>

Options:
  -p, --path PATH                 Base path for mirror operations that write
                                  to disk.
  -o, --overwrite                 Overwrite file/directory when writing to
                                  disk.
  -G, --groups GROUP...           One or multiple groups identified by their
                                  ID, UUID or label.
  --filter-by-last-mirror-time / --no-filter-by-last-mirror-time
                                  Only select nodes whose `mtime` is after the
                                  last mirror time.  [default: filter-by-last-
                                  mirror-time]
  --mirror-processes / --no-mirror-processes
                                  Mirror process data.  [default: mirror-
                                  processes]
  --mirror-data / --no-mirror-data
                                  Mirror data nodes.  [default: no-mirror-
                                  data]
  --only-top-level-calcs / --no-only-top-level-calcs
                                  Mirror calculations in their own dedicated
                                  directories, not just as part of the
                                  mirrored workflow.  [default: only-top-
                                  level-calcs]
  --only-top-level-workflows / --no-only-top-level-workflows
                                  If a top-level workflow calls sub-workflows,
                                  create a designated directory only for the
                                  top-level workflow.  [default: only-top-
                                  level-workflows]
  --delete-missing / --no-delete-missing
                                  If a previously mirrored node is deleted
                                  from AiiDA's DB, also delete the
                                  corresponding mirror directory.  [default:
                                  no-delete-missing]
  --symlink-calcs / --no-symlink-calcs
                                  Symlink workflow sub-calculations to their
                                  own dedicated directories.  [default: no-
                                  symlink-calcs]
  --symlink-between-groups / --no-symlink-between-groups
                                  Symlink data if the same node is contained
                                  in multiple groups.  [default: no-symlink-
                                  between-groups]
  --organize-by-groups / --no-organize-by-groups
                                  If the collection of nodes to be mirrored is
                                  organized in groups, reproduce its
                                  hierarchy.  [default: organize-by-groups]
  --only-groups / --no-only-groups
                                  Mirror only data of nodes which are already
                                  organized in groups.  [default: no-only-
                                  groups]
  --update-groups / --no-update-groups
                                  Update directories if nodes have been added
                                  to other groups, or organized differently in
                                  terms of groups.  [default: no-update-
                                  groups]
  --include-inputs / --exclude-inputs
                                  Include linked input nodes of
                                  `CalculationNode`(s).  [default: include-
                                  inputs]
  --include-outputs / --exclude-outputs
                                  Include linked output nodes of
                                  `CalculationNode`(s).  [default: exclude-
                                  outputs]
  --include-attributes / --exclude-attributes
                                  Include attributes in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  attributes]
  --include-extras / --exclude-extras
                                  Include extras in the
                                  `.aiida_node_metadata.yaml` written for
                                  every `ProcessNode`.  [default: include-
                                  extras]
  -f, --flat                      Mirror files in a flat directory for every
                                  step of a workflow.
  --mirror-unsealed / --no-mirror-unsealed
                                  Also allow the mirroring of unsealed process
                                  nodes.  [default: no-mirror-unsealed]
  -v, --verbosity [notset|debug|info|report|warning|error|critical]
                                  Set the verbosity of the output.
  -h, --help                      Show this message and exit.

</details>

The additional options are `--groups`, `--symlink-between-groups`, `--organize-by-groups`, `--only-groups`, and
`--update-groups`, and, therefore control mainly the behavior of groups in the profile during mirroring.

The final list of options is rather lengthy, but, worry not, sensible defaults have been chosen and should be fine in
most cases.
The default mirroring command will result in a self-contained, logical directory structure, ready for sharing.

## Some examples

### Mirroring groups

Documentation for the `verdi process mirror` feature is already available
[here](https://aiida.readthedocs.io/projects/aiida-core/en/latest/howto/data.html#dumping-data-to-disk), thus we will
first focus on the other two commands `verdi group mirror`. Assume you have an AiiDA profile with the following groups:

```
❯ verdi group list -C
Report: To show groups of all types, use the `-a/--all` option.
  PK  Label               Type string    User               Node count
----  ------------------  -------------  ---------------  ------------
   1  add-group           core           aiida@localhost             1
   2  multiply-add-group  core           aiida@localhost             1
```

Where `add-group` contains one `ArithmeticAddCalculation` and `multiply-add-group` contains one `MultiplyAddWorkchain`.
Running `verdi group mirror 1` gives:

```
❯ verdi group mirror 1
Report: Mirroring data of group `add-group` at path `add-group-mirror`.
Report: Incremental mirroring selected. Will update directory.
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 1 calculations...
Report: No (new) workflows to mirror in group `add-group`.
Success: Raw files for `add-group` <1> mirrored into folder `add-group-mirror`.
```

with the following output directory structure:

```
❯ tree add-group-mirror/
add-group-mirror
└── calculations
   └── ArithmeticAddCalculation-4
      ├── inputs
      │  ├── _aiidasubmit.sh
      │  └── aiida.in
      ├── node_inputs
      └── outputs
         ├── _scheduler-stderr.txt
         ├── _scheduler-stdout.txt
         └── aiida.out
```

Similarly, for the `multiply-add-group`:

```
❯ verdi group mirror 2
Report: Mirroring data of group `multiply-add-group` at path `multiply-add-group-mirror`.
Report: Incremental mirroring selected. Will update directory.
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: No (new) calculations to mirror in group `multiply-add-group`.
Report: Mirroring 1 workflows...
Success: Raw files for group `multiply-add-group` <2> mirrored into folder `multiply-add-group-mirror`.
```

with the directory:

```
❯ tree multiply-add-group-mirror/
multiply-add-group-mirror
└── workflows
   └── MultiplyAddWorkChain-11
      ├── 01-multiply-12
      │  ├── inputs
      │  │  └── source_file
      │  └── node_inputs
      └── 02-ArithmeticAddCalculation-14
         ├── inputs
         │  ├── _aiidasubmit.sh
         │  └── aiida.in
         ├── node_inputs
         └── outputs
            ├── _scheduler-stderr.txt
            ├── _scheduler-stdout.txt
            └── aiida.out
```

The output directory is the group `label`, appended by `mirror`, created in the CWD.
This can, of course, be changed by passing the `--path` argument.
In this directory, depending on the type of process, directories for each `ProcessNode` are placed in `calculations` or
`workflows` subdirectories.

### Mirroring the entire profile

Mirroring the data of the entire profile proceeds as follows:

```
❯ verdi profile mirror
Report: Mirroring data of profile `readme` at path: `profile-readme-mirror`.
Report: Incremental mirroring selected. Will update directory.
Report: Mirroring processes not in any group for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: No (new) calculations to mirror in group `no-group`.
Report: No (new) workflows to mirror in group `no-group`.
Report: Mirroring processes in group `add-group` for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 1 calculations...
Report: No (new) workflows to mirror in group `add-group`.
Report: Mirroring processes in group `multiply-add-group` for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: No (new) calculations to mirror in group `multiply-add-group`.
Report: Mirroring 1 workflows...
Success: Raw files for profile `readme` mirrored into folder `profile-readme-mirror`.
```

and gives the directory tree:

```
❯ tree profile-readme-mirror/
profile-readme-mirror
├── groups
│  ├── add-group
│  │  └── calculations
│  │     └── ArithmeticAddCalculation-4
│  │        ├── inputs
│  │        │  ├── _aiidasubmit.sh
│  │        │  └── aiida.in
│  │        ├── node_inputs
│  │        └── outputs
│  │           ├── _scheduler-stderr.txt
│  │           ├── _scheduler-stdout.txt
│  │           └── aiida.out
│  └── multiply-add-group
│     └── workflows
│        └── MultiplyAddWorkChain-11
│           ├── 01-multiply-12
│           │  ├── inputs
│           │  │  └── source_file
│           │  └── node_inputs
│           └── 02-ArithmeticAddCalculation-14
│              ├── inputs
│              │  ├── _aiidasubmit.sh
│              │  └── aiida.in
│              ├── node_inputs
│              └── outputs
│                 ├── _scheduler-stderr.txt
│                 ├── _scheduler-stdout.txt
│                 └── aiida.out
└── no-group
```

Thus, the `verdi profile mirror` command respects your internal AiiDA data organization in groups.

### JSON mirror log file

If we have a closer look and show also the hidden files:

```
❯ tree -a add-group-mirror/
add-group-mirror
├── .aiida_mirror_safeguard
├── .aiida_mirror_log.json
└── calculations
   └── ArithmeticAddCalculation-4
      ├── .aiida_node_metadata.yaml
      ├── .aiida_mirror_safeguard
      ├── inputs
      │  ├── .aiida
      │  │  ├── calcinfo.json
      │  │  └── job_tmpl.json
      │  ├── _aiidasubmit.sh
      │  └── aiida.in
      ├── node_inputs
      └── outputs
         ├── _scheduler-stderr.txt
         ├── _scheduler-stdout.txt
         └── aiida.out
```

we can see that the hidden `.aiida` directory from the working directory of the simulation is also available under the
`inputs` subdirectory of the calcuulation.

In addition, the top-level output directory `add-group-mirror` contains the `.aiida_mirror_log.json` file that keeps a history
of the nodes that are mirrored to disk, and is therefore essential for incremental mirroring.
For the mirror of the `add-group`, it holds the following content:

```json=
{
    "calculations": {
        "57a1e7ce-c845-47e8-a940-786a91540a09": {
            "path": "/home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/readme/add-group-mirror/calculations/ArithmeticAddCalculation-4",
            "time": "2025-04-01T11:51:33.001012+02:00",
            "links": []
        }
    },
    "workflows": {},
    "groups": {
        "aa13ae86-d6c5-4d2c-94e4-3d42d9619012": {
            "path": "/home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/readme/add-group-mirror",
            "time": "2025-04-01T11:51:32.881287+02:00",
            "links": []
        }
    },
    "data": {}
}
```

Thus the file keeps track of the `path`, (mirror) `time`, and (sym) `links` for mirrored `calculations`, `workflows`,
`groups`, and `data`.
More info about the JSON log file will be outlined further below.

### Safety when overwriting

You can also see that an `.aiida_mirror_safeguard` file is contained in every directory created by the mirror feature for each ORM entitity.
This file serves as a (surprise...) safeguard file, as, in `overwrite` mode, the `mirror` command option performs a dangerous recursive deletion operation of a previous output directory.
If, for whatever reason, the directory that is supposed to be cleaned by the mirror feature in `overwrite` mode is _not_
the correct one, the command will abort if it does not find the `.aiida_mirror_safeguard` file, thus ensuring the
command doesn't accidentally delete your family photo album.
So don't touch that file!!

### Efficient incremental mirroring

Now that we have already mirrored each group and we didn't add any new nodes, if we run the mirror command again:

```
❯ verdi group mirror 1
Report: Mirroring data of group `add-group` at path `add-group-mirror`.
Report: Incremental mirroring selected. Will update directory.
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: No (new) calculations to mirror in group `add-group`.
Report: No (new) workflows to mirror in group `add-group`.
Success: Raw files for group `add-group` <1> mirrored into folder `add-group-mirror`.
```

it should finish almost instantaneously, as there are no new simulations to mirror.

The evaluation of new nodes that should be mirrored is based on the entries in the `.aiida_mirror_log.json` file and the
last time the `mirror` command was run. This information is used to construct a `QueryBuilder` instance that
extracts the relevant nodes from the database.
As this step is the very first one done in the code, and the query is executed using SQL, incremental mirroring for a small number of simulations should be
quick, even for a large database.
The first time a large database is mirrored, however, depending on the number of nodes, might take a considerable amount of time, due to the many individual I/O operations to write the relevant files for each process.

#### Customizing `verdi [group|profile] mirrror`

As mentioned above, we have the following CLI options when mirroring AiiDA groups:

```
  --filter-by-last-mirror-time / --no-filter-by-last-mirror-time
                                  Only select nodes whose `mtime` is after the
                                  last mirror time.  [default: filter-by-last-
                                  mirror-time]
  --mirror-processes / --no-mirror-processes
                                  Mirror process data.  [default: mirror-
                                  processes]
  --mirror-data / --no-mirror-data
                                  Mirror data nodes.  [default: no-mirror-
                                  data]
  --delete-missing / --no-delete-missing
                                  If a previously mirrored node is deleted
                                  from AiiDA's DB, also delete the
                                  corresponding mirror directory.  [default:
                                  no-delete-missing]
  --only-top-level-calcs / --no-only-top-level-calcs
                                  Mirror calculations in their own dedicated
                                  directories, not just as part of the
                                  mirrored workflow.  [default: only-top-
                                  level-calcs]
  --only-top-level-workflows / --no-only-top-level-workflows
                                  If a top-level workflow calls sub-workflows,
                                  create a designated directory only for the
                                  top-level workflow.  [default: only-top-
                                  level-workflows]
  --symlink-calcs / --no-symlink-calcs
                                  Symlink workflow sub-calculations to their
                                  own dedicated directories.  [default: no-
                                  symlink-calcs]
```

Let's consider how they change the behavior one by one.

<!-- first filter, mirror-proc, and mirror-data -->

##### `only-top-level-calcs`/`only-top-level-workflows`

One thing you might have already noticed is that even though the `MultiplyAddWorkchain` calls both, a `multiply`
`calcfunction`, as well as an `ArithmeticAdd` `CalcJob`, there is no `calculations` subdirectory in the `add-group-mirror`
output directory, and, instead, only one `MultiplyAddWorkChain` subdirectory under the `workflows` directory.
This is because, by default, only top-level workflows and calculations (meaning they don't have a `CALLER`) are put into their own, separate directories.
During mirroring, these top-level processes are then traversed recursively, and the files written. Thus, no extra
top-level output directory for the `ArithmeticAddCalculation` called by the `MultiplyAddWorkChain` is required, as it is
mirrored into a subdirectory of the `MultiplyAddWorkChain` output folder.
If you want to obtain _all_ calculations and workflows of your group/profile in the dedicated `calculations` and
`workflows` directories, you can use the `--no-only-top-level-calcs` and/or `--no-only-top-level-workflows` flags.
In that case, the report from running the command indicates that, in addition to the 1 workflow we've seen before, also
2 calculations are being mirrored for the `multiply-add-group`:

```
❯ verdi group mirror multiply-add-group -o --no-only-top-level-calcs
Report: Mirroring data of group `multiply-add-group` at path `multiply-add-group-mirror`.
Report: Overwriting selected. Will clean directory first.
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 2 calculations...
Report: Mirroring 1 workflows...
Success: Raw files for group `multiply-add-group` <2> mirrored into folder `multiply-add-group-mirror`.
```

The resulting directory structure looks like this:

```
❯ tree -D multiply-add-group-mirror/
multiply-add-group-mirror
├── calculations
│  ├── ArithmeticAddCalculation-14
│  │  ├── inputs
│  │  ├── node_inputs
│  │  └── outputs
│  └── multiply-12
│     ├── inputs
│     └── node_inputs
└── workflows
   └── MultiplyAddWorkChain-11
      ├── 01-multiply-12
      │  ├── inputs
      │  └── node_inputs
      └── 02-ArithmeticAddCalculation-14
         ├── inputs
         ├── node_inputs
         └── outputs
```

This means you have _all_ calculations and workflows of the group directly accessible in the `calculations` and
`workflows` directories, rather than inside the nested sub-directories of the top-level workflows.

For instance for a complex `SelfConsistentHubbardWorkChain`:

<details>
<summary><code>verdi process status 590</code></summary>
```
SelfConsistentHubbardWorkChain<590> Finished [0] [2:run_results]
    ├── PwBaseWorkChain<229> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<356> Finished [0]
    │   └── PwCalculation<643> Finished [0]
    ├── PwBaseWorkChain<301> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<734> Finished [0]
    │   └── PwCalculation<278> Finished [0]
    ├── HpWorkChain<826> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<611> Finished [0]
    │   └── HpParallelizeAtomsWorkChain<878> Finished [0] [6:results]
    │       ├── HpBaseWorkChain<397> Finished [0] [3:results]
    │       │   └── HpCalculation<647> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<428> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<762> Finished [0] [3:results]
    │       │   │   └── HpCalculation<994> Finished [0]
    │       │   ├── HpBaseWorkChain<659> Finished [0] [3:results]
    │       │   │   └── HpCalculation<504> Finished [0]
    │       │   ├── HpBaseWorkChain<256> Finished [0] [3:results]
    │       │   │   └── HpCalculation<612> Finished [0]
    │       │   ├── HpBaseWorkChain<685> Finished [0] [3:results]
    │       │   │   └── HpCalculation<54> Finished [0]
    │       │   ├── HpBaseWorkChain<276> Finished [0] [3:results]
    │       │   │   └── HpCalculation<216> Finished [0]
    │       │   ├── HpBaseWorkChain<280> Finished [0] [3:results]
    │       │   │   └── HpCalculation<32> Finished [0]
    │       │   ├── HpBaseWorkChain<975> Finished [0] [3:results]
    │       │   │   └── HpCalculation<551> Finished [0]
    │       │   ├── HpBaseWorkChain<807> Finished [0] [3:results]
    │       │   │   └── HpCalculation<957> Finished [0]
    │       │   ├── HpBaseWorkChain<732> Finished [0] [3:results]
    │       │   │   └── HpCalculation<136> Finished [0]
    │       │   └── HpBaseWorkChain<121> Finished [0] [3:results]
    │       │       └── HpCalculation<318> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<918> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<596> Finished [0] [3:results]
    │       │   │   └── HpCalculation<613> Finished [0]
    │       │   ├── HpBaseWorkChain<666> Finished [0] [3:results]
    │       │   │   └── HpCalculation<179> Finished [0]
    │       │   ├── HpBaseWorkChain<836> Finished [0] [3:results]
    │       │   │   └── HpCalculation<124> Finished [0]
    │       │   ├── HpBaseWorkChain<795> Finished [0] [3:results]
    │       │   │   └── HpCalculation<66> Finished [0]
    │       │   ├── HpBaseWorkChain<245> Finished [0] [3:results]
    │       │   │   └── HpCalculation<211> Finished [0]
    │       │   ├── HpBaseWorkChain<315> Finished [0] [3:results]
    │       │   │   └── HpCalculation<463> Finished [0]
    │       │   ├── HpBaseWorkChain<723> Finished [0] [3:results]
    │       │   │   └── HpCalculation<687> Finished [0]
    │       │   ├── HpBaseWorkChain<453> Finished [0] [3:results]
    │       │   │   └── HpCalculation<709> Finished [0]
    │       │   ├── HpBaseWorkChain<172> Finished [0] [3:results]
    │       │   │   └── HpCalculation<715> Finished [0]
    │       │   └── HpBaseWorkChain<349> Finished [0] [3:results]
    │       │       └── HpCalculation<74> Finished [0]
    │       └── HpBaseWorkChain<744> Finished [0] [3:results]
    │           └── HpCalculation<100> Finished [0]
    ├── structure_relabel_kinds<247> Finished [0]
    ├── PwRelaxWorkChain<680> Finished [0] [3:results]
    │   ├── PwBaseWorkChain<736> Finished [501] [2:while_(should_run_process)(2:inspect_process)]
    │   │   ├── create_kpoints_from_distance<993> Finished [0]
    │   │   └── PwCalculation<583> Finished [501]
    │   └── PwBaseWorkChain<869> Finished [0] [3:results]
    │       ├── create_kpoints_from_distance<521> Finished [0]
    │       └── PwCalculation<119> Finished [0]
    ├── PwBaseWorkChain<472> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<263> Finished [0]
    │   └── PwCalculation<814> Finished [0]
    ├── HpWorkChain<811> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<713> Finished [0]
    │   └── HpParallelizeAtomsWorkChain<331> Finished [0] [6:results]
    │       ├── HpBaseWorkChain<36> Finished [0] [3:results]
    │       │   └── HpCalculation<915> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<563> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<42> Finished [0] [3:results]
    │       │   │   └── HpCalculation<634> Finished [0]
    │       │   ├── HpBaseWorkChain<259> Finished [0] [3:results]
    │       │   │   └── HpCalculation<383> Finished [0]
    │       │   ├── HpBaseWorkChain<650> Finished [0] [3:results]
    │       │   │   └── HpCalculation<661> Finished [0]
    │       │   ├── HpBaseWorkChain<822> Finished [0] [3:results]
    │       │   │   └── HpCalculation<933> Finished [0]
    │       │   ├── HpBaseWorkChain<310> Finished [0] [3:results]
    │       │   │   └── HpCalculation<515> Finished [0]
    │       │   ├── HpBaseWorkChain<148> Finished [0] [3:results]
    │       │   │   └── HpCalculation<345> Finished [0]
    │       │   ├── HpBaseWorkChain<27> Finished [0] [3:results]
    │       │   │   └── HpCalculation<316> Finished [0]
    │       │   ├── HpBaseWorkChain<426> Finished [0] [3:results]
    │       │   │   └── HpCalculation<508> Finished [0]
    │       │   ├── HpBaseWorkChain<384> Finished [0] [3:results]
    │       │   │   └── HpCalculation<435> Finished [0]
    │       │   └── HpBaseWorkChain<219> Finished [0] [3:results]
    │       │       └── HpCalculation<144> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<286> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<466> Finished [0] [3:results]
    │       │   │   └── HpCalculation<657> Finished [0]
    │       │   ├── HpBaseWorkChain<608> Finished [0] [3:results]
    │       │   │   └── HpCalculation<578> Finished [0]
    │       │   ├── HpBaseWorkChain<52> Finished [0] [3:results]
    │       │   │   └── HpCalculation<238> Finished [0]
    │       │   ├── HpBaseWorkChain<214> Finished [0] [3:results]
    │       │   │   ├── HpCalculation<170> Finished [462]
    │       │   │   └── HpCalculation<920> Finished [0]
    │       │   ├── HpBaseWorkChain<283> Finished [0] [3:results]
    │       │   │   └── HpCalculation<109> Finished [0]
    │       │   ├── HpBaseWorkChain<525> Finished [0] [3:results]
    │       │   │   └── HpCalculation<588> Finished [0]
    │       │   ├── HpBaseWorkChain<640> Finished [0] [3:results]
    │       │   │   └── HpCalculation<408> Finished [0]
    │       │   ├── HpBaseWorkChain<56> Finished [0] [3:results]
    │       │   │   └── HpCalculation<619> Finished [0]
    │       │   ├── HpBaseWorkChain<486> Finished [0] [3:results]
    │       │   │   └── HpCalculation<883> Finished [0]
    │       │   └── HpBaseWorkChain<168> Finished [0] [3:results]
    │       │       └── HpCalculation<921> Finished [0]
    │       └── HpBaseWorkChain<159> Finished [0] [3:results]
    │           └── HpCalculation<30> Finished [0]
    ├── PwRelaxWorkChain<402> Finished [0] [3:results]
    │   ├── PwBaseWorkChain<897> Finished [0] [3:results]
    │   │   ├── create_kpoints_from_distance<984> Finished [0]
    │   │   ├── PwCalculation<200> Finished [503]
    │   │   └── PwCalculation<323> Finished [0]
    │   └── PwBaseWorkChain<495> Finished [0] [3:results]
    │       ├── create_kpoints_from_distance<476> Finished [0]
    │       └── PwCalculation<683> Finished [0]
    ├── PwBaseWorkChain<499> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<152> Finished [0]
    │   └── PwCalculation<730> Finished [0]
    ├── HpWorkChain<519> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<609> Finished [0]
    │   └── HpParallelizeAtomsWorkChain<75> Finished [0] [6:results]
    │       ├── HpBaseWorkChain<886> Finished [0] [3:results]
    │       │   └── HpCalculation<207> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<534> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<899> Finished [0] [3:results]
    │       │   │   └── HpCalculation<1013> Finished [0]
    │       │   ├── HpBaseWorkChain<764> Finished [0] [3:results]
    │       │   │   └── HpCalculation<914> Finished [0]
    │       │   ├── HpBaseWorkChain<153> Finished [0] [3:results]
    │       │   │   └── HpCalculation<620> Finished [0]
    │       │   ├── HpBaseWorkChain<793> Finished [0] [3:results]
    │       │   │   └── HpCalculation<112> Finished [0]
    │       │   ├── HpBaseWorkChain<916> Finished [0] [3:results]
    │       │   │   └── HpCalculation<633> Finished [0]
    │       │   ├── HpBaseWorkChain<724> Finished [0] [3:results]
    │       │   │   └── HpCalculation<246> Finished [0]
    │       │   ├── HpBaseWorkChain<338> Finished [0] [3:results]
    │       │   │   └── HpCalculation<555> Finished [0]
    │       │   ├── HpBaseWorkChain<941> Finished [0] [3:results]
    │       │   │   └── HpCalculation<995> Finished [0]
    │       │   ├── HpBaseWorkChain<782> Finished [0] [3:results]
    │       │   │   └── HpCalculation<442> Finished [0]
    │       │   └── HpBaseWorkChain<169> Finished [0] [3:results]
    │       │       └── HpCalculation<892> Finished [0]
    │       ├── HpParallelizeQpointsWorkChain<579> Finished [0] [5:results]
    │       │   ├── HpBaseWorkChain<199> Finished [0] [3:results]
    │       │   │   └── HpCalculation<585> Finished [0]
    │       │   ├── HpBaseWorkChain<616> Finished [0] [3:results]
    │       │   │   └── HpCalculation<679> Finished [0]
    │       │   ├── HpBaseWorkChain<33> Finished [0] [3:results]
    │       │   │   └── HpCalculation<693> Finished [0]
    │       │   ├── HpBaseWorkChain<498> Finished [0] [3:results]
    │       │   │   └── HpCalculation<357> Finished [0]
    │       │   ├── HpBaseWorkChain<45> Finished [0] [3:results]
    │       │   │   └── HpCalculation<104> Finished [0]
    │       │   ├── HpBaseWorkChain<955> Finished [0] [3:results]
    │       │   │   └── HpCalculation<156> Finished [0]
    │       │   ├── HpBaseWorkChain<369> Finished [0] [3:results]
    │       │   │   └── HpCalculation<468> Finished [0]
    │       │   ├── HpBaseWorkChain<284> Finished [0] [3:results]
    │       │   │   └── HpCalculation<215> Finished [0]
    │       │   ├── HpBaseWorkChain<751> Finished [0] [3:results]
    │       │   │   └── HpCalculation<942> Finished [0]
    │       │   └── HpBaseWorkChain<874> Finished [0] [3:results]
    │       │       └── HpCalculation<600> Finished [0]
    │       └── HpBaseWorkChain<178> Finished [0] [3:results]
    │           └── HpCalculation<622> Finished [0]
    ├── PwRelaxWorkChain<606> Finished [0] [3:results]
    │   ├── PwBaseWorkChain<566> Finished [0] [3:results]
    │   │   ├── create_kpoints_from_distance<305> Finished [0]
    │   │   └── PwCalculation<423> Finished [0]
    │   └── PwBaseWorkChain<209> Finished [0] [3:results]
    │       ├── create_kpoints_from_distance<998> Finished [0]
    │       └── PwCalculation<843> Finished [0]
    ├── PwBaseWorkChain<181> Finished [0] [3:results]
    │   ├── create_kpoints_from_distance<186> Finished [0]
    │   └── PwCalculation<368> Finished [0]
    └── HpWorkChain<799> Finished [0] [3:results]
        ├── create_kpoints_from_distance<688> Finished [0]
        └── HpParallelizeAtomsWorkChain<294> Finished [0] [6:results]
            ├── HpBaseWorkChain<320> Finished [0] [3:results]
            │   └── HpCalculation<134> Finished [0]
            ├── HpParallelizeQpointsWorkChain<665> Finished [0] [5:results]
            │   ├── HpBaseWorkChain<823> Finished [0] [3:results]
            │   │   └── HpCalculation<91> Finished [0]
            │   ├── HpBaseWorkChain<123> Finished [0] [3:results]
            │   │   └── HpCalculation<452> Finished [0]
            │   ├── HpBaseWorkChain<870> Finished [0] [3:results]
            │   │   └── HpCalculation<461> Finished [0]
            │   ├── HpBaseWorkChain<382> Finished [0] [3:results]
            │   │   └── HpCalculation<983> Finished [0]
            │   ├── HpBaseWorkChain<146> Finished [0] [3:results]
            │   │   └── HpCalculation<29> Finished [0]
            │   ├── HpBaseWorkChain<887> Finished [0] [3:results]
            │   │   └── HpCalculation<1003> Finished [0]
            │   ├── HpBaseWorkChain<561> Finished [0] [3:results]
            │   │   └── HpCalculation<40> Finished [0]
            │   ├── HpBaseWorkChain<741> Finished [0] [3:results]
            │   │   └── HpCalculation<133> Finished [0]
            │   ├── HpBaseWorkChain<761> Finished [0] [3:results]
            │   │   └── HpCalculation<355> Finished [0]
            │   └── HpBaseWorkChain<1062> Finished [0] [3:results]
            │       └── HpCalculation<1070> Finished [0]
            ├── HpParallelizeQpointsWorkChain<80> Finished [0] [5:results]
            │   ├── HpBaseWorkChain<399> Finished [0] [3:results]
            │   │   └── HpCalculation<371> Finished [0]
            │   ├── HpBaseWorkChain<84> Finished [0] [3:results]
            │   │   └── HpCalculation<63> Finished [0]
            │   ├── HpBaseWorkChain<753> Finished [0] [3:results]
            │   │   └── HpCalculation<367> Finished [0]
            │   ├── HpBaseWorkChain<405> Finished [0] [3:results]
            │   │   └── HpCalculation<410> Finished [0]
            │   ├── HpBaseWorkChain<295> Finished [0] [3:results]
            │   │   └── HpCalculation<964> Finished [0]
            │   ├── HpBaseWorkChain<24> Finished [0] [3:results]
            │   │   └── HpCalculation<1024> Finished [0]
            │   ├── HpBaseWorkChain<844> Finished [0] [3:results]
            │   │   └── HpCalculation<1025> Finished [0]
            │   ├── HpBaseWorkChain<255> Finished [0] [3:results]
            │   │   └── HpCalculation<1056> Finished [0]
            │   ├── HpBaseWorkChain<403> Finished [0] [3:results]
            │   │   └── HpCalculation<1040> Finished [0]
            │   └── HpBaseWorkChain<1063> Finished [0] [3:results]
            │       └── HpCalculation<1028> Finished [0]
            └── HpBaseWorkChain<1042> Finished [0] [3:results]
                └── HpCalculation<1034> Finished [0]
```

</details>

<!-- region -->

<details>
<summary>Mirror of a `SelfconsistentHubbardWorkchain`</summary>

```
group-hubbard-mirror/workflows/SelfConsistentHubbardWorkChain-590
├── 01-iteration_01_scf_smearing-PwBaseWorkChain-229
│  ├── 01-create_kpoints_from_distance-356
│  │  ├── inputs
│  │  └── node_inputs
│  │     └── structure
│  └── 02-iteration_01-PwCalculation-643
│     ├── inputs
│     ├── node_inputs
│     │  ├── pseudos
│     │  │  ├── Mn
│     │  │  ├── O0
│     │  │  └── O1
│     │  └── structure
│     └── outputs
├── 02-iteration_01_scf_fixed_magnetic-PwBaseWorkChain-301
│  ├── 01-create_kpoints_from_distance-734
│  │  ├── inputs
│  │  └── node_inputs
│  │     └── structure
│  └── 02-iteration_01-PwCalculation-278
│     ├── inputs
│     ├── node_inputs
│     │  ├── pseudos
│     │  │  ├── Mn
│     │  │  ├── O0
│     │  │  └── O1
│     │  └── structure
│     └── outputs
├── 03-iteration_01_hp-HpWorkChain-826
│  ├── 01-create_qpoints_from_distance-create_kpoints_from_distance-611
│  │  ├── inputs
│  │  └── node_inputs
│  │     └── structure
│  └── 02-iteration_01_hp-HpParallelizeAtomsWorkChain-878
│     ├── 01-initialization-HpBaseWorkChain-397
│     │  └── 01-iteration_01-HpCalculation-647
│     │     ├── inputs
│     │     ├── node_inputs
│     │     │  └── hubbard_structure
│     │     └── outputs

... (this continues for another >1k lines)

```

</details>

<!-- endregion -->

Running the command with the flags `--no-only-top-level-workflows` and
`--no-only-top-level-calcs` makes access to the relevant sub-calculations and workflows easier:

<details><summary>Top-level `ls` on processes of the SelfConsistentHubbardWorkChain</summary>
![alt text](figs/image-1.png)
</details>


##### `--symlink-calcs`

Using the flag `--no-only-top-level-calcs`, calculations are being mirrored in their own, dedicated directories, under
`calculations`. This is in addition to subdirectories that were created for these `CalculationNode`s in the mirror
directories of the `WorkflowNode`s from which they were called (if so).
This can lead to data duplication, which is why the `--symlink-calcs` flag can be used to symlink the mirror directories of
the calculations to the subdirectories of the parent workflows:

```
❯ verdi group mirror multiply-add-group -o --no-only-top-level-calcs --symlink-calcs
Report: Mirroring data of group `multiply-add-group` at path `multiply-add-group-mirror`.
Report: Overwriting selected. Will clean directory first.
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 2 calculations...
Report: Mirroring 1 workflows...
Success: Raw files for group `multiply-add-group` <2> mirrored into folder `multiply-add-group-mirror`.
```

giving the following directory:

```
❯ tree multiply-add-group-mirror/
multiply-add-group-mirror
├── calculations
│  ├── ArithmeticAddCalculation-14
│  │  ├── inputs
│  │  │  ├── _aiidasubmit.sh
│  │  │  └── aiida.in
│  │  ├── node_inputs
│  │  └── outputs
│  │     ├── _scheduler-stderr.txt
│  │     ├── _scheduler-stdout.txt
│  │     └── aiida.out
│  └── multiply-12
│     ├── inputs
│     │  └── source_file
│     └── node_inputs
└── workflows
   └── MultiplyAddWorkChain-11
      ├── 01-multiply-12 -> /home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/multiply-add-group-mirror/calculations/multiply-12
      └── 02-ArithmeticAddCalculation-14 -> /home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/multiply-add-group-mirror/calculations/ArithmeticAddCalculation-14
```
</details>

Here, the sub-calculations of the `MultiplyAddWorkChain` are symlinked to the relevant directories in the `calculations`
directory.
The symlinking also works between different groups, if, for example, calculations are contained in multiple groups (this
is because to evaluate the possibility for symlinking, the global `MirrorLogger` that keeps track of mirrored entities
and the corresponding paths is checked).

For instance, for the current demonstration profile:

```
❯ verdi profile mirror --no-only-top-level-calcs --symlink-calcs -o
Report: Mirroring data of profile `readme` at path `profile-readme-mirror`.
Report: Overwriting selected. Will clean directory first.
Report: Mirroring processes in group `add-group` for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 2 calculations...
Report: No (new) workflows to mirror in group `add-group`.
Report: Mirroring processes in group `multiply-add-group` for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: Mirroring 2 calculations...
Report: Mirroring 1 workflows...
Report: Mirroring processes not in any group for profile `readme`...
Report: Collecting nodes from the database. For the first mirror, this can take a while.
Report: No (new) calculations to mirror in group `no-group`.
Report: No (new) workflows to mirror in group `no-group`.
Success: Raw files for profile `readme` mirrored into folder `profile-readme-mirror`.
```

we obtain:

```
❯ tree profile-readme-mirror/
profile-readme-mirror
├── groups
│  ├── add-group
│  │  └── calculations
│  │     ├── ArithmeticAddCalculation-4
│  │     │  ├── inputs
│  │     │  │  ├── _aiidasubmit.sh
│  │     │  │  └── aiida.in
│  │     │  ├── node_inputs
│  │     │  └── outputs
│  │     │     ├── _scheduler-stderr.txt
│  │     │     ├── _scheduler-stdout.txt
│  │     │     └── aiida.out
│  │     └── ArithmeticAddCalculation-14
│  │        ├── inputs
│  │        │  ├── _aiidasubmit.sh
│  │        │  └── aiida.in
│  │        ├── node_inputs
│  │        └── outputs
│  │           ├── _scheduler-stderr.txt
│  │           ├── _scheduler-stdout.txt
│  │           └── aiida.out
│  └── multiply-add-group
│     ├── calculations
│     │  ├── ArithmeticAddCalculation-14 -> /home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/readme/profile-readme-mirror/groups/add-group/calculations/ArithmeticAddCalculation-14
│     │  └── multiply-12
│     │     ├── inputs
│     │     │  └── source_file
│     │     └── node_inputs
│     └── workflows
│        └── MultiplyAddWorkChain-11
│           ├── 01-multiply-12 -> /home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/readme/profile-readme-mirror/groups/multiply-add-group/calculations/multiply-12
│           └── 02-ArithmeticAddCalculation-14 -> /home/geiger_j/aiida_projects/verdi-profile-dump/dev-dumps/readme/profile-readme-mirror/groups/multiply-add-group/calculations/ArithmeticAddCalculation-14
└── no-group
```

where the `ArithmeticAddCalculation` with pk=14 is symlinked to the corresponding `calculations` directory of the
`add-group`.
Please note that while the symlinking feature is useful for data deduplication, individual subdirectories are **not**
self-contained. This means that you __cannot__ zip the `multipply-add-group` directory and send it, as it will be
missing the symlinked calculations.
Evaluate for yourself if that is a price you are willing to pay for the achieved data deduplication.
We intend to provide fully self-contained output directories with the feature, which is why the `--symlink-calcs` option
is turned off by default.

#### Customizing `verdi profile mirrror`



## Python API


##