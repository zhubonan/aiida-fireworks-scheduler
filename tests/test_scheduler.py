"""
Test for the scheduler
"""

import pytest
from pathlib import Path

from fireworks.core.rocket_launcher import launch_rocket
from aiida_fireengine.fscheduler import FwJobResource, FwScheduler
from aiida_fireengine.jobs import AiiDAJobFirework
import shutil

@pytest.fixture
def dummy_job(clean_launchpad):
    """Create a dummy job"""

    job = AiiDAJobFirework('localhost', '/tmp/aiida-test', 
                           1,
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
    launch_rocket(launchpad, fw_id=job_id)

    assert (ldir / 'bar').exists()
    assert (ldir / '_scheduler-stdout.txt').exists()
    assert (ldir / '_scheduler-stderr.txt').exists()

    # Clean up the tempdiretory
    shutil.rmtree(str(ldir))
