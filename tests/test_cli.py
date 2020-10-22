"""
Test the commandline interface module
"""
from pathlib import Path
import tempfile
import shutil

import pytest

from click.testing import CliRunner
from aiida_fireworks_scheduler.cmdline import generate_worker, duplicate_fe

# pylint: disable=import-outside-toplevel,no-member,redefined-outer-name
LOCALHOST_NAME = 'localhost-test'

EXECUTABLE = {
    'arithmetic.add': 'bash',
}


def get_path_to_executable(executable):
    """ Get path to local executable.
    :param executable: Name of executable in the $PATH variable
    :type executable: str
    :return: path to executable
    :rtype: str
    """
    path = shutil.which(executable)
    if path is None:
        raise ValueError(
            "'{}' executable not found in PATH.".format(executable))
    return path


def get_computer(name=LOCALHOST_NAME, workdir=None):
    """Get AiiDA computer.
    Loads computer 'name' from the database, if exists.
    Sets up local computer 'name', if it isn't found in the DB.

    :param name: Name of computer to load or set up.
    :param workdir: path to work directory
        Used only when creating a new computer.
    :return: The computer node
    :rtype: :py:class:`aiida.orm.Computer`
    """
    from aiida.orm import Computer
    from aiida.common.exceptions import NotExistent

    try:
        computer = Computer.objects.get(label=name)
    except NotExistent:
        if workdir is None:
            workdir = tempfile.mkdtemp()

        computer = Computer(
            label=name,
            description='localhost computer set up by aiida_diff tests',
            hostname=name,
            workdir=workdir,
            transport_type='local',
            scheduler_type='direct')
        computer.store()
        computer.set_minimum_job_poll_interval(0.)
        computer.configure()

    return computer


def get_code(entry_point, computer):
    """Get local code.
    Sets up code for given entry point on given computer.

    :param entry_point: Entry point of calculation plugin
    :param computer: (local) AiiDA computer
    :return: The code node
    :rtype: :py:class:`aiida.orm.Code`
    """
    from aiida.orm import Code, QueryBuilder, Computer

    try:
        executable = EXECUTABLE[entry_point]
    except KeyError:
        raise KeyError(
            "Entry point '{}' not recognized. Allowed values: {}".format(
                entry_point, list(EXECUTABLE.keys())))

    qbuilder = QueryBuilder()
    qbuilder.append(Computer, filters={'id': computer.pk})
    qbuilder.append(Code,
                    with_computer=Computer,
                    filters={'label': executable})
    codes = [_[0] for _ in qbuilder.all()]
    if codes:
        return codes[0]

    path = get_path_to_executable(executable)
    code = Code(
        input_plugin_name=entry_point,
        remote_computer_exec=[computer, path],
    )
    code.label = executable
    return code.store()


@pytest.fixture
def cmd_test_env(clear_database_auto):
    """Prepare the testing environment"""
    _ = clear_database_auto
    localhost = get_computer("localhost")
    code = get_code("arithmetic.add", localhost)
    return code


def test_duplicate(cmd_test_env):
    """Test the duplicate command"""
    from aiida.orm import Computer, Code
    _ = cmd_test_env
    runner = CliRunner()

    runner.invoke(duplicate_fe, ["-Y", "localhost"], catch_exceptions=False)
    assert Computer.get(label='localhost-fw')

    runner.invoke(duplicate_fe, ["-Y", "localhost", "--suffix", 'fe'],
                  catch_exceptions=False)
    assert Computer.get(label='localhost-fe')

    runner.invoke(duplicate_fe,
                  ["-Y", "localhost", "--suffix", 'fc', '--include-codes'],
                  catch_exceptions=False)
    assert Computer.get(label='localhost-fc')
    assert Code.get_from_string("bash@localhost-fc")


def test_worker(cmd_test_env):
    """Test worker command"""
    from aiida_fireworks_scheduler.fworker import AiiDAFWorker, DEFAULT_USERNAME
    runner = CliRunner()
    _ = cmd_test_env

    with runner.isolated_filesystem() as workdir:

        runner.invoke(generate_worker,
                      ['-Y', 'localhost', '--mpinp', '4', 'myworker.yaml'],
                      catch_exceptions=False)
        assert not (Path(workdir) / 'myworker.yaml').exists()

        runner.invoke(duplicate_fe, ["-Y", "localhost"],
                      catch_exceptions=False)
        runner.invoke(generate_worker,
                      ['-Y', 'localhost-fw', '--mpinp', '4', 'myworker.yaml'],
                      catch_exceptions=False)
        worker = AiiDAFWorker.from_file(str(Path(workdir) / "myworker.yaml"))

        assert worker.computer_id == "localhost"
        assert worker.username == DEFAULT_USERNAME
        assert worker.mpinp == 4
