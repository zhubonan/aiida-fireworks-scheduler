"""
Specialised scheduler to interface with Fireworks
"""

from datetime import datetime
import os

from fireworks.core.launchpad import LaunchPad
from fireworks.fw_config import LAUNCHPAD_LOC

import aiida.schedulers
from aiida.common.exceptions import FeatureNotAvailable
from aiida.common.folders import SandboxFolder
from aiida.common.extendeddicts import AttributeDict
from aiida.common.escaping import escape_for_bash
from aiida.schedulers import Scheduler
from aiida.schedulers import SchedulerError, SchedulerParsingError
from aiida.schedulers.datastructures import (JobInfo, JobState,
                                             ParEnvJobResource)

from aiida_fireworks_scheduler.jobs import AiiDAJobFirework
from aiida_fireworks_scheduler.common import DEFAULT_USERNAME

# pylint: disable=protected-access,too-many-locals

_MAP_STATUS_FW = {
    'PAUSED': JobState.QUEUED_HELD,
    'WAITING': JobState.QUEUED,
    'READY': JobState.QUEUED,
    'RESERVED': JobState.QUEUED,
    'RUNNING': JobState.RUNNING,
    'COMPLETED': JobState.DONE,
    'ARCHIVED': JobState.UNDETERMINED,
    'DEFUSED': JobState.SUSPENDED,
    # Usually FIZZLED is an indication of having some problems,
    # set it to UNDETERMINED to allow further investigations
    'FIZZLED': JobState.UNDETERMINED
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


class FwScheduler(Scheduler):
    """
    Scheduler that interfaces with `fireworks.LaunchPad`
    """
    _logger = aiida.schedulers.Scheduler._logger.getChild('Fw')

    _features = {
        'can_query_by_user': False,  # Cannot query by user - only by just list
    }

    _job_resource_class = FwJobResource
    _lpad = None
    FRESH_ENV = True

    def __init__(self, launchpad=None):
        super().__init__()
        # Here store the launchpad in the class attribute so it can be reused....
        if launchpad is not None:
            self.lpad = launchpad
            # Keep the launchpad
            FwScheduler._lpad = launchpad
        else:
            # Create and save the launchpad
            if FwScheduler._lpad is None:
                FwScheduler._lpad = LaunchPad.from_file(LAUNCHPAD_LOC)
            self.lpad = FwScheduler._lpad

    def get_jobs(self, jobs=None, user=None, as_dict=False):
        """
        Return the list of currently active jobs
        """
        computer_id = self.transport._machine  # Host name is used as the identifier
        lpad = self.lpad

        query = {
            "spec._aiida_job_info.computer_id":
            computer_id,  # Limit to this machine
            # Ignore completed and archived jobs
            "state": {
                "$not": {
                    "$in": ["COMPLETED", "ARCHIVED"]
                }
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
            # Get the information of the fireworks in the dict format
            # this is more robust than getting Fireworks objects
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

        # The username only makes sense for SSH transport
        try:
            username = self.transport._connect_args['username']
        except AttributeError:
            username = DEFAULT_USERNAME

        firework = AiiDAJobFirework(
            computer_id=self.transport._machine,
            username=username,
            remote_work_dir=working_directory,
            job_name=options['job_name'],
            submit_script_name=submit_script,
            mpinp=options['mpinp'],
            walltime=options['walltime'],
            stderr_fname=options['stderr_fname'],
            stdout_fname=options['stdout_fname'],
            priority=options['priority'],
            fresh_env=self.FRESH_ENV,
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
        except Exception as error:  # pylint: disable=broad-except
            self.logger.error(
                f"Cannot find the relevant fireworks.\n Error {error.args}")
            return False

        # If the job is running - request to stop the job by putting a AIIDA_STOP file
        # in the working directory
        if fw_dict['state'] == 'RUNNING':
            try:
                launch_dir = fw_dict['spec']['_aiida_job_info'][
                    'remote_work_dir']
                stop_file = os.path.join(launch_dir, 'AIIDA_STOP')
                result = self.transport.exec_command_wait(f'touch {stop_file}')
                if result[0] == 0:
                    return True
                self.logger.error(
                    f"Remote command execution failed.\nSTDERR captured: {result[2]}"
                )
                return False
            except Exception as error:  # pylint: disable=broad-except
                self.logger.error(
                    f"Error placing AIIDA_STOP file.\nError {error}")
                return False
        # Otherwise just defuse the job in the launchpad
        else:
            try:
                firework = self.lpad.defuse_fw(int(jobid))
            except Exception as error:  # pylint: disable=broad-except
                self.logger.error(
                    f"Error defusing waiting Firework.\nError {error}")
                return False
            else:
                return bool(firework)

    def get_detailed_job_info(self, job_id):
        """
        Getting detailed job information. Does not make sense for this scheduler
        """
        raise FeatureNotAvailable

    def _get_submit_script_header(self, job_tmpl):
        """
        Return the submit script header, using the parameters from the
        job_tmpl.

        Args:
           job_tmpl: an JobTemplate instance with relevant parameters set.

        Modified and simplied based on that of the SGE scheduler.
        We need to write the scheduler headers because they will be read in the
        *upload* step later to submit the job to fireworks' MongoDB server.
        """
        # pylint: disable=too-many-statements,too-many-branches

        empty_line = ''

        lines = []

        # I keep it here - it may be a feature we can exploit later
        if job_tmpl.submit_as_hold:
            # if isinstance(job_tmpl.submit_as_hold, str):
            lines.append(f'#$ -h {job_tmpl.submit_as_hold}')

        # leave the name of the job as it is
        if job_tmpl.job_name:

            lines.append(f'#$ -N {job_tmpl.job_name}')

        if job_tmpl.sched_output_path:
            lines.append(f'#$ -o {job_tmpl.sched_output_path}')

        if job_tmpl.sched_error_path:
            lines.append(f'#$ -e {job_tmpl.sched_error_path}')

        if job_tmpl.priority:
            # Priority of the job.  Format: host-dependent integer.  Default:
            # zero.   Range:  [-1023,  +1024].  Sets job's Priority
            # attribute to priority.
            lines.append(f'#$ -p {job_tmpl.priority}')

        if not job_tmpl.job_resource:
            raise ValueError(
                'Job resources (as the tot_num_mpiprocs) are required for the SGE scheduler plugin'
            )
        # Setting up the parallel environment
        lines.append(
            f'#$ -pe {str(job_tmpl.job_resource.parallel_env)} {int(job_tmpl.job_resource.tot_num_mpiprocs)}'
        )

        if job_tmpl.max_wallclock_seconds is not None:
            try:
                tot_secs = int(job_tmpl.max_wallclock_seconds)
                if tot_secs <= 0:
                    raise ValueError
            except ValueError:
                raise ValueError(
                    'max_wallclock_seconds must be '
                    "a positive integer (in seconds)! It is instead '{}'"
                    ''.format((job_tmpl.max_wallclock_seconds)))
            hours = tot_secs // 3600
            tot_minutes = tot_secs % 3600
            minutes = tot_minutes // 60
            seconds = tot_minutes % 60
            lines.append(f'#$ -l h_rt={hours:02d}:{minutes:02d}:{seconds:02d}')

        if job_tmpl.custom_scheduler_commands:
            lines.append(job_tmpl.custom_scheduler_commands)

        # TAKEN FROM PBSPRO:
        # Job environment variables are to be set on one single line.
        # This is a tough job due to the escaping of commas, etc.
        # moreover, I am having issues making it work.
        # Therefore, I assume that this is bash and export variables by
        # and.
        if job_tmpl.job_environment:
            lines.append(empty_line)
            lines.append('# ENVIRONMENT VARIABLES BEGIN ###')
            if not isinstance(job_tmpl.job_environment, dict):
                raise ValueError(
                    'If you provide job_environment, it must be a dictionary')
            for key, value in job_tmpl.job_environment.items():
                lines.append(f'export {key.strip()}={escape_for_bash(value)}')
            lines.append('# ENVIRONMENT VARIABLES  END  ###')
            lines.append(empty_line)

        return '\n'.join(lines)

    # Methods need for transport-based interfaes - not used here
    def _get_submit_command(self, submit_script):
        raise FeatureNotAvailable

    def _parse_submit_output(self, retval, stdout, stderr):
        raise FeatureNotAvailable

    def _get_kill_command(self, jobid):
        raise FeatureNotAvailable

    def _parse_kill_output(self, retval, stdout, stderr):
        raise FeatureNotAvailable

    def _parse_joblist_output(self, retval, stdout, stderr):
        raise FeatureNotAvailable

    def _get_joblist_command(self, jobs=None, user=None):
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
            hours, minutes, seconds = timestring.split(':')
            seconds = int(seconds) + int(minutes) * 60 + int(hours) * 3600
            options['walltime'] = int(seconds)

        if '#$ -p ' in line:
            options['priority'] += int(line.split()[-1])
    required_fields = ['job_name', 'mpinp', 'walltime']

    missing = [field for field in required_fields if field not in options]
    if missing:
        raise SchedulerParsingError(
            f"Missing fields: {missing} while parsing the job script")

    return options


class FwSchedulerKeepEnv(FwScheduler):
    """
    A FW-base scheduler that runs the `_aiidasubmit.sh` in the same environment as the submission
    script.

    This mode of operation is needed by SLURM which uses `srun` directives to launch job steps.
    """
    FRESH_ENV = False
