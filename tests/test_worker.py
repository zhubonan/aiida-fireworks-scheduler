"""
Test the AiiDAFWorker
"""

import pytest
from aiida_fireworks_scheduler.fworker import AiiDAFWorker, DEFAULT_USERNAME
# pylint: disable=redefined-outer-name


@pytest.fixture
def worker():
    """A worker"""
    return AiiDAFWorker("localhost", username='user', mpinp=4, category='test')


def test_worker_query(worker):
    """Test generated queries for the worker"""
    query = worker.query

    assert "$or" in query

    fw_query = query["$or"][1]['$and'][0]
    fw_walltime_query = query["$or"][1]['$and'][1]
    aiida_query = query["$or"][0]

    assert fw_query['spec._category']['$ne'] == 'AIIDA_RESERVED_CATEGORY'
    assert fw_query['spec._category']['$eq'] == 'test'
    assert fw_walltime_query['$or'][0] == {
        'spec._walltime_seconds': {
            '$exists': False
        }
    }
    assert fw_walltime_query['$or'][1] == {
        'spec._walltime_seconds': {
            '$lt': 2591940
        }
    }

    assert aiida_query['spec._aiida_job_info.walltime'][
        '$lt'] == worker.sch_aware.get_remaining_seconds(
        ) - worker.SECONDS_SAFE_INTERVAL
    assert aiida_query['spec._aiida_job_info.computer_id'] == 'localhost'
    assert aiida_query['spec._aiida_job_info.mpinp'] == 4
    assert aiida_query['spec._aiida_job_info.username'] == 'user'


def test_worker_serialise(worker):
    """Test serialiseation of the worker"""

    worker_dict = worker.to_dict()
    worker_dict['computer_id'] = 'remote'
    worker2 = AiiDAFWorker.from_dict(worker_dict)
    assert worker2.computer_id == 'remote'

    worker_dict.pop("username")
    worker2 = AiiDAFWorker.from_dict(worker_dict)
    assert worker2.username == DEFAULT_USERNAME
