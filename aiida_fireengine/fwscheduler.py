"""
Specialised scheduler to interface with Fireworks
"""

from datetime import datetime, timedelta
import os

from fireworks.core.launchpad import LaunchPad
from fireworks.fw_config import LAUNCHPAD_LOC

import aiida.schedulers
from aiida.common.exceptions import FeatureNotAvailable
from aiida.common.folders import SandboxFolder
from aiida.common.extendeddicts import AttributeDict
from aiida.schedulers.plugins.sge import SgeScheduler
from aiida.schedulers import SchedulerError, SchedulerParsingError
from aiida.schedulers.datastructures import (JobInfo, JobState,
                                             ParEnvJobResource)

from aiida_fireengine.jobs import AiiDAJobFirework

# pylint: disable=protected-access,too-many-locals

_MAP_STATUS_FW = {
    'PAUSED': JobState.QUEUED_HELD,
    'WAITING': JobState.QUEUED,
    'READY': JobState.QUEUED,
    'RESERVED': JobState.QUEUED,
    'RUNNING': JobState.RUNNING
}


class FwJobResource(ParEnvJobResource):
    """
    `JobResource` for the FwScheduler based on `ParEnvJobResource`.
    The difference is that the default `parallel_env` file default to "mpi" here,
    and it is OK to have it not set.
    """
    @classmethod
    def validate_resources(cls, **kwargs):
        """Validate the resources against the job resource class of this scheduler.

        :param kwargs: dictionary of values to define the job resources
        :return: attribute dictionary with the parsed parameters populated
        :raises ValueError: if the resources are invalid or incomplete
        """
        resources = AttributeDict()

        resources.parallel_env = kwargs.pop('parallel_env', 'mpi')

        try:
            resources.tot_num_mpiprocs = int(kwargs.pop('tot_num_mpiprocs'))
        except (KeyError, ValueError):
            raise ValueError(
                '`tot_num_mpiprocs` must be specified and must be an integer')

        if resources.tot_num_mpiprocs < 1:
            raise ValueError(
                '`tot_num_mpiprocs` must be greater than or equal to one.')

        if kwargs:
            raise ValueError('these parameters were not recognized: {}'.format(
                ', '.join(list(kwargs.keys()))))

        return resources


class FwScheduler(SgeScheduler):
    """
    Scheduler that interfaces with `fireworks.LaunchPad`
    """
    _logger = aiida.schedulers.Scheduler._logger.getChild('Fw')

    _features = {
        'can_query_by_user': False,  # Cannot query by user - only by just list
    }

    _job_resource_class = FwJobResource

    def __init__(self, launchpad=None):
        super().__init__()
        if launchpad is None:
            self.lpad = LaunchPad.from_file(LAUNCHPAD_LOC)
        else:
            self.lpad = launchpad

    def get_jobs(self, jobs=None, user=None, as_dict=False):
        """
        Return the list of currently active jobs
        """
        computer_id = self.transport._machine  # Host name is used as the identifier
        lpad = self.lpad

        query = {
            "spec._aiida_job_info.computer_id":
            computer_id,  # Limit to this machine
            "state": {
                "$in": ["PAUSED", "WAITING", "READY", "RESERVED", "RUNNING"]
            }
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
            this_job.job_id = str(fid)
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
                this_job.submission_time = datetime.strptime(
                    fw_dict['created_on'], "%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                pass
            # NOTE: add information about the dispatch time by looking into the launches

            joblist.append(this_job)

        if as_dict:
            jobdict = {job.job_id: job for job in joblist}
            if None in jobdict:
                raise SchedulerError('Found at least one job without jobid')
            return jobdict

        return joblist

    def submit_from_script(self, working_directory, submit_script):
        """Submit the submission script to the scheduler

        This will create a WorkFlow for the job using the provided script and working
        directory and submit it to the LaunchPad.

        :return: return a string with the job ID in a valid format to be used for querying.
        """
        self.transport.chdir(working_directory)
        with SandboxFolder() as sandbox:
            self.transport.getfile(submit_script,
                                   sandbox.get_abs_path(submit_script))
            options = parse_sge_script(sandbox.get_abs_path(submit_script))

        firework = AiiDAJobFirework(
            computer_id=self.transport._machine,
            username=self.transport._connect_args['username'],
            remote_work_dir=working_directory,
            job_name=options['job_name'],
            submit_script_name=submit_script,
            mpinp=options['mpinp'],
            walltime=options['walltime'],
            stderr_fname=options['stderr_fname'],
            stdout_fname=options['stdout_fname'],
            priority=options['priority'],
        )

        mapping = self.lpad.add_wf(firework)
        return str(list(mapping.values())
                   [0])  # This is a string of the FW id assigned to the job

    def kill(self, jobid):
        """Defuse a job in the LaunchPad

        Note, for fireworks this only works for queued jobs. Need to think about how to
        kill running ones....
        """
        try:
            fw_dict = self.lpad.get_fw_dict_by_id(int(jobid))
        except Exception:  # pylint: disable=broad-except
            return False

        # If the job is running - request to stop the job by putting a AIIDA_STOP file
        # in the working directory
        if fw_dict['state'] == 'RUNNING':
            try:
                launch_dir = fw_dict['spec']['_aiida_job_info'][
                    '_remote_work_dir']
                stop_file = os.path.join(launch_dir, 'AIIDA_STOP')
                self.transport.exec_command_wait(f'touch {stop_file}')
                return True
            except Exception:  # pylint: disable=broad-except
                return False
        # Otherwise just defuse the job in the launchpad
        else:
            try:
                firework = self.lpad.defuse_fw(int(jobid))
            except Exception:  # pylint: disable=broad-except
                return False
            else:
                return bool(firework)

    def get_detailed_job_info(self, job_id):
        """
        Getting detailed job information. Does not make sense for this scheduler
        """
        raise FeatureNotAvailable


def parse_sge_script(local_script_path):
    """
    Parse the SGE script

    :returns: A dictionary of the options for constructing AiiDAJobFirework
    """

    with open(local_script_path) as handle:
        lines = handle.readlines()

    options = {
        'stdout_fname': '_scheduler-stdout.txt',
        'stderr_fname': '_scheduler-stderr.txt',
        'priority':
        100,  # Base priority of AiiDA jobs in the FW system, hard coded to 100 for now
    }

    for line in lines:
        if '#$ -N' in line:
            options['job_name'] = line.split()[-1]  # Name of the job
        if '#$ -o' in line:
            options['stdout_fname'] = line.replace("#$ -o", "").strip()
        if '#$ -e' in line:
            options['stderr_fname'] = line.replace("#$ -e", "").strip()
        if '#$ -pe' in line:
            options['mpinp'] = int(line.split()[-1])
        if 'h_rt' in line:
            timestring = line.split('=')[1].strip()
            runtime = datetime.strptime(timestring, "%H:%M:%S")
            runtime = timedelta(hours=runtime.hour,
                                minutes=runtime.minute,
                                seconds=runtime.second)
            options['walltime'] = int(runtime.total_seconds())
        if '#$ -p ' in line:
            options['priority'] += int(line.split()[-1])
    required_fields = ['job_name', 'mpinp', 'walltime']

    missing = [field for field in required_fields if field not in options]
    if missing:
        raise SchedulerParsingError(
            f"Missing fields: {missing} while parsing the job script")

    return options
