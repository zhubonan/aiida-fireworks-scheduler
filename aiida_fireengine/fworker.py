"""
Class for specialised worker for running AiiDA jobs
include multiprocessing (mpinp) and walltime limit in the query
"""

import json
import six

from fireworks.core.fworker import FWorker
from fireworks.utilities.fw_serializers import recursive_serialize, \
    recursive_deserialize, DATETIME_HANDLER

from aiida_fireengine.awareness import SchedulerAwareness


class AiiDAFWorker(FWorker):
    """
    Specialised worker for running AiiDA related jobs
    """
    SECONDS_SAFE_INTERVAL = 60

    def __init__(self, computer_id, username, mpinp, *args, **kwargs):
        """
        Instantiate a AiiDAFWorker object.
        The worker selects the jobs to run using the criteria defined in the
        constructor

        :param computer_id (str): Hostname of the computer
        :param username (str): User name for the computer
        :param mpinp (int): the number of MPI processes to be launched.

        The rest of the arguments will be passed to the `FWorker`.
        """
        self.computer_id = computer_id
        self.username = username
        self.sch_aware = SchedulerAwareness.get_awareness()
        self.mpinp = mpinp
        super().__init__(*args, **kwargs)

    @property
    def query(self):

        # This is the usual conventional stuff
        query_ = dict(self._query)
        fworker_check = [{
            "spec._fworker": {
                "$exists": False
            }
        }, {
            "spec._fworker": None
        }, {
            "spec._fworker": self.name
        }]
        if '$or' in query_:
            query_['$and'] = query_.get('$and', [])
            query_['$and'].extend([{
                '$or': query_.pop('$or')
            }, {
                '$or': fworker_check
            }])
        else:
            query_['$or'] = fworker_check
        if self.category and isinstance(self.category, six.string_types):
            if self.category == "__none__":
                query_['spec._category'] = {"$exists": False}
            else:
                query_['spec._category'] = {"$eq": self.category}
        elif self.category:  # category is list of str
            query_['spec._category'] = {"$in": self.category}
        # Do not match any AIIDA_RESERVED_CATEGORY jobs - those jobs should be matched by
        # specific conditions as defined below
        query_['spec._category']['$ne'] = "AIIDA_RESERVED_CATEGORY"

        # AiiDA related queries
        query_aiida = {
            'spec._aiida_job_info.mpinp': self.mpinp,
            'spec._aiida_job_info.computer_id': self.computer_id,
            'spec._aiida_job_info.username': self.username,
            'spec._aiida_job_info.walltime': {
                '$lt': self.seconds_left - self.SECONDS_SAFE_INTERVAL
            }
        }

        # Need to satisfy either of the two sub queries
        return {'$or': [query_aiida, query_]}

    @property
    def seconds_left(self):
        """
        How long this job is going to be alive.
        """
        return self.sch_aware.get_remaining_seconds()

    @recursive_serialize
    def to_dict(self):
        return {
            'name': self.name,
            'category': self.category,
            'query': json.dumps(self._query, default=DATETIME_HANDLER),
            'env': self.env,
            'computer_id': self.computer_id,
            'username': self.username,
            'mpinp': self.mpinp,
        }

    @classmethod
    @recursive_deserialize
    def from_dict(cls, m_dict):
        return AiiDAFWorker(computer_id=m_dict['computer_id'],
                            username=m_dict['username'],
                            mpinp=m_dict['mpinp'],
                            name=m_dict['name'],
                            category=m_dict['category'],
                            query=json.loads(m_dict['query']),
                            env=m_dict.get("env"))
