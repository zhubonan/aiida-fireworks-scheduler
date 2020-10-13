"""
Specialised scheduler to interface with Fireworks
"""

import datetime
from aiida.common.exceptions import FeatureNotAvailable
from aiida.schedulers.plugins.sge import SgeScheduler
from aiida.schedulers import SchedulerError, SchedulerParsingError
from aiida.schedulers.datastructures import (JobInfo, JobState, ParEnvJobResource)

from fireworks.core.launchpad import LaunchPad
from fireworks.fw_config import LAUNCHPAD_LOC

_MAP_STATUS_FW = {
    'PAUSED': JobState.QUEUED_HELD,
    'WAITING': JobState.QUEUED,
    'READY': JobState.QUEUED,
    'RESERVED': JobState.QUEUED,
    'RUNNING': JobState.RUNNING
}

class FwJobResource(ParEnvJobResource):
    pass

class FwScheduler(SgeScheduler):
    """
    Scheduler that interfaces with `fireworks.LaunchPad`
    """

    def __init__(self):
        super().__init__()
        self.lpad = LaunchPad.from_file(LAUNCHPAD_LOC)
        
    def get_jobs(self, jobs=None, user=None, as_dict=False):
        """
        Return the list of currently active jobs
        """
        computer_id = self.transport._machine  # Host name is used as the identifier
        lpad = self.lpad
        query = {
            "spec._aiida_computer": computer_id,
            "state": {"$in": ["PAUSED", "WAITING", "READY", "RESERVED", "RUNNING"]}
        }
        
        fw_ids = lpad.get_fw_ids(query)
        joblist = []
        for fid in fw_ids:
            # Get the information of the fireworks in the dict format this is more robust
            # than instantiation
            try:
                fw_dict = lpad.get_fw_dict_by_id(fid)
            except ValueError:
                raise SchedulerError(f"No FW found for id: {fid}")

            spec = fw_dict.get("spec", {})

            this_job = JobInfo()
            this_job.job_id = fid
            try:
                this_job.job_state = _MAP_STATUS_FW[fw_dict['state']]
            except IndexError:
                this_job.job_state = JobState.UNDETERMINED

            this_job.title = fw_dict.get('name')
            category = spec.get('category')
            if isinstance(category, str):
                this_job.queue_name = category
            elif isinstance(category, (tuple, list)):
                this_job.queue_name = ":".join(category)
            
            try:
                this_job.submission_time = datetime.datetime.strptime(fw_dict['created_on'], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                pass

            joblist.append(this_job)
        return joblist
    

    def submit_from_script(self, working_directory, submit_script):
        """Submit the submission script to the scheduler

        This will create a WorkFlow for the job using the provided script and working
        directory and submit it to the LaunchPad.

        :return: return a string with the job ID in a valid format to be used for querying.
        """

        workflow = self._get_workflow_from_script(working_directory, submit_script)
        self.lpad.add_wf(workflow)

    def kill(self, jobid):
        """Defuse a job in the LaunchPad

        Note, for fireworks this only works for queued jobs. Need to think about how to 
        kill running ones....
        """
        try:
            fw = self.lpad.defuse_fw(jobid)
        except Exception:
            return False
        else:
            if fw:
                return True
            else:
                return False

    def _get_workflow_from_script(self, working_directory, submit_script):
        """
        This method parses the submit script for the crucial information such as the job
        run time and job names etc and build the WorkFlow accordingly

        Things to be parsed:
        
        - timelimit
        - number of cores
        - job_name

        :return: return a ``WorkFlow`` that is ready to be submitted to the ``LaunchPad``
        """
        raise NotImplementedError


    def get_detailed_job_info(self, job_id):
        """
        Getting detailed job information. Does not make sense for this scheduler
        """
        raise FeatureNotAvailable