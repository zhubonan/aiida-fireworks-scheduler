"""
Test for the scheduler
"""

import pytest
from pathlib import Path
import tempfile
import contextlib
import os

from aiida.common.extendeddicts import AttributeDict
from fireworks.core.rocket_launcher import launch_rocket
from aiida_fireengine.fscheduler import FwJobResource, FwScheduler, parse_sge_script
from aiida_fireengine.jobs import AiiDAJobFirework
from aiida.schedulers.datastructures import (JobInfo, JobState, ParEnvJobResource)
import shutil

TEST_DIR = os.path.dirname(os.path.realpath(__file__))

@contextlib.contextmanager
def keep_cwd():
    """Context manager for keeping the current working directory"""
    cwd = os.getcwd()
    yield cwd
    os.chdir(cwd)


@pytest.fixture
def dummy_job(clean_launchpad):
    """Create a dummy job"""

    job = AiiDAJobFirework('localhost', '/tmp/aiida-test', 
                           'aiida-1',
                           '_aiidasubmit.sh',
                           walltime=1800,
                           mpinp=2,
                           stdout_fname='_scheduler-stdout.txt',
                           stderr_fname='_scheduler-stderr.txt')

    job_id = clean_launchpad.add_wf(job)
    return job_id


def test_job_init(dummy_job, launchpad):
    """Test insertion of a job"""
    lpad = launchpad
    job_id = list(dummy_job.values())[0]
    fw_dict = lpad.get_fw_dict_by_id(job_id)
    assert fw_dict['spec']['_aiida_job_info']['computer_id'] == 'localhost'
    script_content = fw_dict['spec']['_tasks'][0]['script']
    assert script_content == 'chmod +x _aiidasubmit.sh && ./_aiidasubmit.sh > _scheduler-stdout.txt 2> _scheduler-stderr.txt'
    

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
    assert jobs[0].job_id == fw_id
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
    assert len(jobs) == 0

def test_parse_script():
    """Test parsing script"""
    options = parse_sge_script( (Path(TEST_DIR) / 'data') / '_aiidasubmit.sh')

    assert options['job_name'] == 'aiida-340981'
    assert options['stdout_fname'] == '_scheduler-stdout.txt'
    assert options['stderr_fname'] == '_scheduler-stderr.txt'
    assert options['mpinp'] == 24
    assert options['walltime'] == 8 * 3600
