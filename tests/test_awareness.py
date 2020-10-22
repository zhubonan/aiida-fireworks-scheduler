"""
Tests for the awareness module
"""
import os

import pytest
from aiida_fireworks_scheduler.awareness import DummyAwareness, SGEAwareness, SlurmAwareness


def test_dummy():
    """Test for the DummyAwareness"""
    aware = DummyAwareness()
    assert aware.get_remaining_seconds() > 0


def test_sge():
    """Not a comprehensive test yet"""
    aware = SGEAwareness()
    assert aware.is_in_job is False

    os.environ["JOB_ID"] = "123"
    with pytest.raises(Exception):
        aware = SGEAwareness()
    os.environ.pop("JOB_ID")


def test_slurm():
    """Not a comprehensive test yet"""
    aware = SlurmAwareness()
    assert aware.is_in_job is False

    os.environ["SLURM_JOB_ID"] = "123"
    with pytest.raises(Exception):
        aware = SlurmAwareness()
    os.environ.pop("SLURM_JOB_ID")
