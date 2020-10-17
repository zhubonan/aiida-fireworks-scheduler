[![Build Status](https://github.com/zhubonan/aiida-fireengine/workflows/ci/badge.svg?branch=master)](https://github.com/zhubonan/aiida-fireengine/actions)
[![Coverage Status](https://coveralls.io/repos/github/zhubonan/aiida-fireengine/badge.svg?branch=master)](https://coveralls.io/github/zhubonan/aiida-fireengine?branch=master)
[![Docs status](https://readthedocs.org/projects/aiida-fireengine/badge)](http://aiida-fireengine.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/aiida-fireengine.svg)](https://badge.fury.io/py/aiida-fireengine)

# aiida-fireengine

AiiDA plugin to allow using `fireworks` as the execution engine for `CalcJob`.

## Repository contents

* [`.github/`](.github/): [Github Actions](https://github.com/features/actions) configuration
  * [`ci.yml`](.github/workflows/ci.yml): runs tests, checks test coverage and builds documentation at every new commit
  * [`publish-on-pypi.yml`](.github/workflows/publish-on-pypi.yml): automatically deploy git tags to PyPI - just generate a [PyPI API token](https://pypi.org/help/#apitoken) for your PyPI account and add it to the `pypi_token` secret of your github repository
* [`aiida_fireengine/`](aiida_fireengine/): The main source code of the plugin package
  * [`fwscheduler.py`](aiida_fireengine/fwscheduler.py): A new `FWScheduler` class.
  * [`scripts/arlauncher.py`](aiida_fireengine/scripts/arlaunch_run.py): A special `rlaunch` script for launching jobs respecting the walltime limits.
  * [`jobs.py`](aiida_fireengine/jobs.py): Specialised `AiiDAJobFirework` for running AiiDA prepared jobs.
  * [`fworker.py`](aiida_fireengine/fworker.py): Specialised `AiiDAFWorker` to generate query for selecting appropriate jobs from the FireServer.
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

* `FWScheduler` Scheduler plugin to submit jobs to LaunchPad managed by `fireworks` package.

* `arlaunch` command for launching jobs on the cluster machine.

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

Note that you must configure the `LAUNCHPAD_LOC` setting pointing to your `my_launchpad.yaml` file on the LOCAL machine. These setting will be picked up by the daemon.

On the remote machine, setup your `my_fworker.yaml` with special directives for identifying the computer and username. Launch jobs use the `arlaunch` command supplied. Note that you will need to install this package on the remote machine.

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
