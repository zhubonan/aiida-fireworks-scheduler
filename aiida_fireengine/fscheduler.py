"""
Specialised scheduler to interface with Fireworks
"""

from datetime import datetime

from aiida.common.exceptions import FeatureNotAvailable
from aiida.common.folders import SandboxFolder
import aiida.schedulers 
from aiida.schedulers.plugins.sge import SgeScheduler
from aiida.schedulers import SchedulerError, SchedulerParsingError
from aiida.schedulers.datastructures import (JobInfo, JobState, ParEnvJobResource)

from fireworks.core.launchpad import LaunchPad
from fireworks.fw_config import LAUNCHPAD_LOC

from aiida_fireengine.jobs import AiiDAJobFirework

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
    _logger = aiida.schedulers.Scheduler._logger.getChild('Fw')

    _features = {
        'can_query_by_user': False,   # Cannot query by user - only by just list
    }

    _job_resource_class = FwJobResource

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
            "spec._aiida_info.computer_id": computer_id,    # Limit to this machine
            "state": {"$in": ["PAUSED", "WAITING", "READY", "RESERVED", "RUNNING"]}
        }

        # Limit to the specific fw_ids
        if jobs:
            # Convert to integer keys
            jobs = [int(job_id) for job_id in jobs]
            query['fw_id'] = {'$in': jobs}                      
        
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

            # Category or categories are mapped to queue_name attribute
            category = spec.get('category')
            if isinstance(category, str):
                this_job.queue_name = category
            elif isinstance(category, (tuple, list)):
                this_job.queue_name = ":".join(category)
            
            # The created_on is mapped to the submission time
            try:
                this_job.submission_time = datetime.datetime.strptime(fw_dict['created_on'], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                pass
            # TODO: add information about the dispatch time by looking into the launches

            joblist.append(this_job)
        return joblist
    

    def submit_from_script(self, working_directory, submit_script):
        """Submit the submission script to the scheduler

        This will create a WorkFlow for the job using the provided script and working
        directory and submit it to the LaunchPad.

        :return: return a string with the job ID in a valid format to be used for querying.
        """
        self.transport.chdir(working_directory)
        with SandboxFolder() as sandbox:
            self.transport.getfile(submit_script, sandbox.get_abs_path(submit_script))

        options = parse_sge_script(working_directory, sandbox.get_abs_path(submit_script))

        firework = AiiDAJobFirework(
            computer_id=self.transport._machine,
            remote_work_dir=working_directory,
            job_name=options['job_name'],
            submit_script_name=submit_script,
            mpinp=options['mpinp'],
            walltime=options['walltime'],
            stderr_fname=options['stderr_fname'],
            stdout_fname=options['stcout_fname']
        ) 

        mapping = self.lpad.add_wf(firework)
        return str(mapping[-1])   # This is a string of the FW id assigned to the job 

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


def parse_sge_script(remote_working_path, local_script_path):
    """
    Parse the SGE script

    :returns: A dictionary of the options for constructing AiiDAJobFirework
    """

    with open(local_script_path) as handle:
        lines = handle.readlines()

    options = {
        'stcout_fname': '_scheduler-stdout.txt',
        'stderr_fname': '_scheduler-stderr.txt',
    }
    for line in lines:
        if '#$ -N' in line:
            options['job_name'] = line.split()[-1]  # Name of the job
        if '#$ -o' in line:
            options['stcout_fname'] = line.replace("#$ -o", "").strip()
        if '#$ -e' in line:
            options['stderr_fname'] = line.replace("#$ -e", "").strip()
        if '#$ -pe' in line:
            options['mpinp'] = int(line.split()[-1])
        if 'h_rt' in line:
            timestring = line.split('=')[1].strip()
            runtime = datetime.strptime(timestring, "%H:%M:%S")
            runtime = datetime.timedelta(hours=runtime.hour, minutes=runtime.minute, seconds=runtime.second)
            options['walltime'] = int(runtime.total_seconds())

    return options
    
