[![Build Status](https://github.com/zhubonan/aiida-fireengine/workflows/ci/badge.svg?branch=master)](https://github.com/zhubonan/aiida-fireengine/actions)
[![Coverage Status](https://coveralls.io/repos/github/zhubonan/aiida-fireengine/badge.svg?branch=master)](https://coveralls.io/github/zhubonan/aiida-fireengine?branch=master)
[![Docs status](https://readthedocs.org/projects/aiida-fireengine/badge)](http://aiida-fireengine.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/aiida-fireengine.svg)](https://badge.fury.io/py/aiida-fireengine)

# aiida-fireengine

AiiDA plugin for using `fireworks` as the execution engine for `CalcJobProcess`.

The main advantage of using the `FwScheduler`, as provided in this plugin, compared to the standard AiiDA scheduler plugins is that it allows more flexible job placement.
For example, your may be forced to submit very large jobs to the cluster (or simply such jobs goes through the queue faster!),
or that the cluster has a strict limit on the number of jobs that can be in the queue.
Using `FwScheduler`, a single allocation of the resources from the scheduler (SGE, PBSpro, SLURM etc.) can be used to run multiple AiiDA `CalcJob`s in serial or in parallel, depending on the user configuration.
In addition, AiiDA jobs can be run along side other workflows in fireworks.


## Repository contents

* [`.github/`](.github/): [Github Actions](https://github.com/features/actions) configuration
  * [`ci.yml`](.github/workflows/ci.yml): runs tests, checks test coverage and builds documentation at every new commit
  * [`publish-on-pypi.yml`](.github/workflows/publish-on-pypi.yml): automatically deploy git tags to PyPI - just generate a [PyPI API token](https://pypi.org/help/#apitoken) for your PyPI account and add it to the `pypi_token` secret of your github repository
* [`aiida_fireworks_scheduler/`](aiida_fireworks_scheduler/): The main source code of the plugin package
  * [`fwscheduler.py`](aiida_fireworks_scheduler/fwscheduler.py): A new `FWScheduler` class.
  * [`scripts/arlauncher.py`](aiida_fireworks_scheduler/scripts/arlaunch_run.py): A special `rlaunch` script for launching jobs respecting the walltime limits.
  * [`jobs.py`](aiida_fireworks_scheduler/jobs.py): Specialised `AiiDAJobFirework` for running AiiDA prepared jobs.
  * [`fworker.py`](aiida_fireworks_scheduler/fworker.py): Specialised `AiiDAFWorker` to generate query for selecting appropriate jobs from the FireServer.
* [`docs/`](docs/): A documentation template ready for publication on [Read the Docs](http://aiida-diff.readthedocs.io/en/latest/)
* [`examples/`](examples/): An example of how to submit a calculation using this plugin
* [`tests/`](tests/): Basic regression tests using the [pytest](https://docs.pytest.org/en/latest/) framework (submitting a calculation, ...). Install `pip install -e .[testing]` and run `pytest`.
* [`.coveragerc`](.coveragerc): Configuration of [coverage.py](https://coverage.readthedocs.io/en/latest) tool reporting which lines of your plugin are covered by tests
* [`.gitignore`](.gitignore): Telling git which files to ignore
* [`.pre-commit-config.yaml`](.pre-commit-config.yaml): Configuration of [pre-commit hooks](https://pre-commit.com/) that sanitize coding style and check for syntax errors. Enable via `pip install -e .[pre-commit] && pre-commit install`
* [`.readthedocs.yml`](.readthedocs.yml): Configuration of documentation build for [Read the Docs](https://readthedocs.org/)
* [`LICENSE`](LICENSE): License for your plugin
* [`MANIFEST.in`](MANIFEST.in): Configure non-Python files to be included for publication on [PyPI](https://pypi.org/)
* [`README.md`](README.md): This file
* [`conftest.py`](conftest.py): Configuration of fixtures for [pytest](https://docs.pytest.org/en/latest/)
* [`pytest.ini`](pytest.ini): Configuration of [pytest](https://docs.pytest.org/en/latest/) test discovery
* [`setup.json`](setup.json): Plugin metadata for registration on [PyPI](https://pypi.org/) and the [AiiDA plugin registry](https://aiidateam.github.io/aiida-registry/) (including entry points)
* [`setup.py`](setup.py): Installation script for pip / [PyPI](https://pypi.org/)

## Features

* `FWScheduler` scheduler plugin to submit jobs to LaunchPad managed by `fireworks`.

* `arlaunch` command for launching jobs on the cluster machine.

* `verdi data fireengine` command line tool for duplicating existing `Computer`/`Cold` for switching to `FwScheduler`.

## Installation

On the local machine where AiiDA is installed:

```shell
pip install aiida-fireengine[local]
```

On the remote machine where jobs to be launched:

```shell
pip install aiida-fireengine
```

## Usage

Simply create a new computer using `verdi computer setup` and select the `fw` scheduler.
Configure your `fireworks` configuration following the guide [here](https://materialsproject.github.io/fireworks/config_tutorial.html).

Note that you must configure the `LAUNCHPAD_LOC` setting in the file as defined by the `FW_CONFIG_FILE` environment variable to point to your `my_launchpad.yaml` file on BOTH the local and remote machines. On the local machine, it will be picked up by the daemon.

In addition, on the remote machine, setup your `my_fworker.yaml` with special directives for identifying the computer and username. These files can be generated using:

```shell
verdi data fireengine generate-worker -Y COMPUTER -mpinp NUM_MPI_PROCESSORS
```

Note that each *worker" can only launch jobs of a particular size (number of MPI processors). But you can always combine multiple workers in one or more cluster jobs.

At runtime, jobs needs to be launched with the `arlaunch` command on the remote machine.

## Development

```shell
git clone https://github.com/zhubonan/aiida-fireengine .
cd aiida-fireengine
pip install -e .[pre-commit,testing]  # install extra dependencies
pre-commit install  # install pre-commit hooks
pytest -v  # discover and run all tests
```

See the [developer guide](http://aiida-fireengine.readthedocs.io/en/latest/developer_guide/index.html) for more information.

## License

MIT

## Contact

zhubonan@outlook.com
