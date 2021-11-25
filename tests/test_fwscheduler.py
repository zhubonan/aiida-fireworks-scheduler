"""
Test for the scheduler
"""

from pathlib import Path
import contextlib
import os
import shutil

import pytest

from fireworks.core.rocket_launcher import launch_rocket

from aiida.common.extendeddicts import AttributeDict
from aiida.schedulers.datastructures import JobInfo, JobState
from aiida.schedulers import SchedulerParsingError

from aiida_fireworks_scheduler.fwscheduler import FwJobResource, FwScheduler, parse_sge_script
from aiida_fireworks_scheduler.jobs import AiiDAJobFirework

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = Path(TEST_DIR) / 'data'

# pylint: disable=redefined-outer-name, unused-argument, no-self-use


@contextlib.contextmanager
def keep_cwd():
    """Context manager for keeping the current working directory"""
    cwd = os.getcwd()
    yield cwd
    os.chdir(cwd)


@pytest.fixture
def dummy_job(clean_launchpad):
    """Create a dummy job"""

    job = AiiDAJobFirework('localhost',
                           'user',
                           '/tmp/aiida-test',
                           'aiida-1',
                           '_aiidasubmit.sh',
                           walltime=1800,
                           mpinp=2,
                           stdout_fname='_scheduler-stdout.txt',
                           stderr_fname='_scheduler-stderr.txt')

    job_id = clean_launchpad.add_wf(job)
    return job_id


@pytest.fixture
def dummy_job_with_env(clean_launchpad):
    """Create a dummy job that keeps the environmental variables"""
    job = AiiDAJobFirework(
        'localhost',
        'user',
        '/tmp/aiida-test',
        'aiida-1',
        '_aiidasubmit.sh',
        walltime=1800,
        mpinp=2,
        stdout_fname='_scheduler-stdout.txt',
        stderr_fname='_scheduler-stderr.txt',
        fresh_env=False,
    )

    job_id = clean_launchpad.add_wf(job)
    return job_id


@pytest.fixture
def short_job(clean_launchpad):
    """Create a dummy job"""

    job = AiiDAJobFirework('localhost',
                           'user',
                           '/tmp/aiida-test',
                           'aiida-1',
                           '_aiidasubmit.sh',
                           walltime=2,
                           mpinp=2,
                           stdout_fname='_scheduler-stdout.txt',
                           stderr_fname='_scheduler-stderr.txt')

    job_id = clean_launchpad.add_wf(job)
    return job_id


def test_fw_resources():
    """Test construction of the FwResource object"""
    res = FwJobResource(tot_num_mpiprocs=8)
    assert res.parallel_env == 'mpi'

    res = FwJobResource(tot_num_mpiprocs=8, parallel_env='mpi')
    assert res.parallel_env == 'mpi'
    assert res.tot_num_mpiprocs == 8

    with pytest.raises(ValueError):
        res = FwJobResource(tot_num_mpiprocs=8, foo='bar', parallel_env='mpi')


def test_job_init(dummy_job, launchpad):
    """Test insertion of a job"""
    lpad = launchpad
    job_id = list(dummy_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['spec']['_aiida_job_info']['computer_id'] == 'localhost'
    script_content = fw_dict['spec']['_tasks'][0]['script']
    assert './_aiidasubmit.sh > _scheduler-stdout.txt 2> _scheduler-stderr.txt &' in script_content


def test_job_run(dummy_job, launchpad):
    """
    Test running a simple job script with
    `echo Foo > bar`.

    """
    lpad = launchpad
    job_id = list(dummy_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)

    ldir = Path(fw_dict['spec']['_launch_dir'])
    assert str(ldir) == '/tmp/aiida-test'

    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / '_aiidasubmit.sh').write_text("echo Foo > bar")
    with keep_cwd():
        launch_rocket(launchpad, fw_id=job_id)

    assert (ldir / 'bar').exists()
    assert (ldir / '_scheduler-stdout.txt').exists()
    assert (ldir / '_scheduler-stderr.txt').exists()

    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['state'] == 'COMPLETED'

    # Clean up the tempdiretory
    shutil.rmtree(str(ldir))


def test_job_run_with_env(dummy_job, launchpad):
    """
    Test running a simple job script with
    `echo Foo > bar`.

    """
    lpad = launchpad
    job_id = list(dummy_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)

    ldir = Path(fw_dict['spec']['_launch_dir'])
    assert str(ldir) == '/tmp/aiida-test'

    ldir.mkdir(parents=True, exist_ok=True)

    (ldir / '_aiidasubmit.sh').write_text("echo $Foo > bar")
    os.environ['Foo'] = 'baz'
    with keep_cwd():
        launch_rocket(launchpad, fw_id=job_id)

    assert (ldir / 'bar').exists()
    assert (ldir / '_scheduler-stdout.txt').exists()
    assert (ldir / '_scheduler-stderr.txt').exists()
    assert (ldir / 'bar').read_text() == 'baz'

    os.environ.pop('Foo')
    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['state'] == 'COMPLETED'

    # Clean up the tempdiretory
    shutil.rmtree(str(ldir))


def test_get_jobs(dummy_job, launchpad):
    """Test the get_jobs method"""

    fw_id = list(dummy_job.values())[0]
    scheduler = FwScheduler(launchpad)
    # Mock the transport object
    scheduler.set_transport(AttributeDict({'_machine': 'localhost'}))

    # List all jobs
    jobs = scheduler.get_jobs()
    assert isinstance(jobs[0], JobInfo)
    assert len(jobs) == 1
    assert jobs[0].job_id == str(fw_id)
    assert jobs[0].title == 'aiida-1'
    assert jobs[0].job_state == JobState.QUEUED
    previous_job = jobs[0]

    # Find the exact job
    jobs = scheduler.get_jobs(jobs=[str(fw_id)])
    assert jobs[0] == previous_job

    # Fire the rocket, now the job should dissapear
    with keep_cwd():
        launch_rocket(launchpad, fw_id=fw_id)
    jobs = scheduler.get_jobs(jobs=[str(fw_id)])
    assert not jobs


def test_parse_script():
    """Test parsing script"""
    options = parse_sge_script((Path(TEST_DIR) / 'data') / '_aiidasubmit.sh')

    assert options['job_name'] == 'aiida-340981'
    assert options['stdout_fname'] == '_scheduler-stdout.txt'
    assert options['stderr_fname'] == '_scheduler-stderr.txt'
    assert options['mpinp'] == 24
    assert options['walltime'] == 8 * 3600

    # Test raising error for incomplete script
    with pytest.raises(SchedulerParsingError):
        options = parse_sge_script(
            (Path(TEST_DIR) / 'data') / '_aiidasubmit_incomplete.sh')


def test_job_kill_while_run(dummy_job, launchpad):
    """
    Test job killing while running. Here run a command that will
    output the AIIDA_STOP file mid-way, making the script getting
    killed mid-way.
    """
    lpad = launchpad
    job_id = list(dummy_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)

    ldir = Path(fw_dict['spec']['_launch_dir'])
    assert str(ldir) == '/tmp/aiida-test'

    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / '_aiidasubmit.sh'
     ).write_text("echo Foo > bar; touch AIIDA_STOP; sleep 10 && touch foo")
    with keep_cwd():
        launch_rocket(launchpad, fw_id=job_id)

    assert (ldir / 'bar').exists()
    assert (ldir / '_scheduler-stdout.txt').exists()
    assert (ldir / '_scheduler-stderr.txt').exists()
    assert not (ldir / 'foo').exists()

    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['state'] == 'COMPLETED'
    assert fw_dict['launches'][0]['action']['stored_data']['returncode'] == 11

    # Clean up the tempdiretory
    shutil.rmtree(str(ldir))


def test_job_timeout(short_job, launchpad):
    """Test the case where a job gets terminated timing out"""

    lpad = launchpad
    job_id = list(short_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)

    ldir = Path(fw_dict['spec']['_launch_dir'])
    assert str(ldir) == '/tmp/aiida-test'

    ldir.mkdir(parents=True, exist_ok=True)
    # Should have bar but not foo, FW job should be COMPLETED
    (ldir /
     '_aiidasubmit.sh').write_text("echo Foo > bar; sleep 3 && touch foo")
    with keep_cwd():
        launch_rocket(launchpad, fw_id=job_id)

    assert (ldir / 'bar').exists()
    assert (ldir / '_scheduler-stdout.txt').exists()
    assert (ldir / '_scheduler-stderr.txt').exists()
    assert not (ldir / 'foo').exists()

    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['state'] == 'COMPLETED'
    assert fw_dict['launches'][0]['action']['stored_data']['returncode'] == 12

    # Clean up the tempdiretory
    shutil.rmtree(str(ldir))


def test_kill(launchpad, dummy_job):
    """Test killing jobs"""

    job_id = str(list(dummy_job.values())[0])
    scheduler = FwScheduler(launchpad)
    assert scheduler.kill(job_id)

    ids = launchpad.get_fw_ids(query={'state': 'READY'})
    assert not ids

    ids = launchpad.get_fw_ids(query={'state': 'DEFUSED'})
    assert len(ids) == 1


def test_submit_job(clean_launchpad, clear_database_auto):
    """Test submitting a job"""
    class MockTrans:
        """Mocking Transport"""
        def __init__(self):
            self._machine = 'localhost'
            self._connect_args = {'username': 'user'}

        def chdir(self, directory):
            """Mock chdir method"""
        def getfile(self, fname, localpath):
            """Fake getfile method"""
            shutil.copy(DATA_DIR / fname, localpath)

    scheduler = FwScheduler(clean_launchpad)
    scheduler.set_transport(MockTrans())
    job_id = scheduler.submit_from_script('foo', '_aiidasubmit.sh')

    assert job_id == '1'

    fw_ids = clean_launchpad.get_fw_ids({})
    assert fw_ids[0] == 1
