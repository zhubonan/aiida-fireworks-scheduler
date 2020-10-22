"""
Runtime scheduler awareness
"""
import subprocess
import os
import re
import tempfile
import logging
from datetime import datetime, timedelta, timezone

LOGGER = logging.getLogger(__name__)


class SchedulerAwareness:
    """Schduler object"""
    def __init__(self, *args, **kwargs):
        """SchedulerAwareness object for accessing information from the scheduler"""
        del args
        del kwargs
        self._job_id = None
        self._ncpus = None

    def get_n_cpus(self):
        """Return the number of CPUS in this job"""
        raise NotImplementedError

    @property
    def user_name(self):
        """Return the name of the current user"""
        return os.environ['USER']

    def get_remaining_seconds(self):
        """Get the remaining time before this job gets killed"""
        raise NotImplementedError

    @property
    def is_in_job(self):
        """Return wether I am in a remote job"""
        if self.job_id is None:
            return False
        return True

    @property
    def job_id(self):
        """ID of the current job"""
        raise NotImplementedError

    @classmethod
    def get_awareness(cls):
        """Automatically get the specialised Awareness instance"""
        for trial in [SlurmAwareness, SGEAwareness, DummyAwareness]:
            obj = trial()
            if obj.is_in_job:
                return obj
        return None


class DummyAwareness(SchedulerAwareness):
    """DummyAwareness for running jobs locally"""
    DEFAULT_REMAINING_TIME = 3600 * 24 * 30

    def __init__(self, *args, **kwargs):
        super(DummyAwareness, self).__init__(*args, **kwargs)
        self._job_id = str('0')

    def get_n_cpus(self):
        return 4

    @property
    def job_id(self):
        return self._job_id

    def get_remaining_seconds(self):
        """Get the remaining time. Default to 30 days"""
        return self.DEFAULT_REMAINING_TIME

    @property
    def is_in_job(self):
        return True


class SGEAwareness(SchedulerAwareness):
    """SGE runtime awareness"""
    def __init__(self, *args, **kwargs):
        """Initialise the SGEAwareness object"""
        super(SGEAwareness, self).__init__(*args, **kwargs)
        if self.is_in_job:
            self._readtask_info()
        self._start_time = None
        self._end_time = None

    @property
    def job_id(self):
        """ID of the job"""
        if self._job_id is None:
            job_id = os.environ.get('JOB_ID')
            task_id = os.environ.get('SGE_TASK_ID')
            if task_id and task_id != 'undefined':
                job_id = job_id + '.' + task_id
                LOGGER.warning(
                    'WARNING: REMAINING TIME IS NOT CORRECT FOR TASK ARRAY')
            self._job_id = job_id
        return self._job_id

    def _readtask_info(self):
        """Read more detailed task infomation"""
        raw_data = subprocess.check_output(
            ['qstat', '-j', f'{self.job_id}'],  # pylint: disable=unexpected-keyword-arg
            universal_newlines=True)
        raw_data = raw_data.split('\n')
        task_info = {}
        for line in raw_data[1:]:
            # Ignore lines that are not in the right format
            try:
                key, value = line.split(':', maxsplit=1)
            except ValueError:
                continue
            task_info[key.strip()] = value.strip()
        self._task_info = task_info

    def get_n_cpus(self):
        """Get the number of CPUS"""
        nslots = os.environ.get('NSLOTS')
        if nslots:
            return int(nslots)
        return None

    def get_max_run_seconds(self):
        """Return the maximum run time in seconds"""
        rlist = self._task_info['hard resource_list']
        match = re.search(r'h_rt=(\d+)', rlist)
        if match:
            return int(match.group(1))
        return None

    def get_end_time(self, refresh=False):
        """Return the time when the job is expected to finish"""
        end_time = self.get_start_time(refresh=refresh) + timedelta(
            seconds=self.get_max_run_seconds())
        return end_time

    def get_start_time(self, refresh=False):
        """Return the start time of this job"""
        if self._start_time is None or refresh:
            output = subprocess.check_output(  # pylint: disable=unexpected-keyword-arg
                ['qstat', '-j', str(self.job_id), '-xml'],
                universal_newlines=True)
            match = re.search(r'<JAT_start_time>(.+)</JAT_start_time>', output)
            if match:
                raw = match.group(1)
                time_int = int(raw)
                # SchedulerAwareness always use UTC time - not may note be true everywhere
                start_time = datetime.utcfromtimestamp(time_int).replace(
                    tzinfo=timezone.utc)
                self._start_time = start_time

        return self._start_time

    def get_remaining_seconds(self):
        """Return the remaining time in seconds"""
        # Everything much be time zone aware to work with BST
        tdelta = self.get_end_time() - datetime.now().astimezone()
        return int(tdelta.total_seconds())


class SlurmAwareness(SchedulerAwareness):
    """SlurmAwareness object for storing and extracting information in slurm"""
    _task_info = None
    _warning = 0

    def __init__(self):
        """Initialise and SlurmAwareness instance"""
        super(SlurmAwareness, self).__init__()
        self.task_info = {}
        if self._task_info is None:
            self._readtask_info()
            self._task_info = self.task_info
        else:
            self.task_info = self._task_info

    @property
    def is_in_job(self):
        """Wether I am in a job"""
        job_id = os.environ.get('SLURM_JOB_ID', None)
        if job_id is None:
            return False
        return True

    @property
    def job_id(self):
        if self._job_id is None:
            self._job_id = os.environ.get('SLURM_JOB_ID')
        return self._job_id

    def _readtask_info(self):
        """A function to extract information from environmental variables
        SLURM_JOB_ID unique to each job
        Return an dictionnary contain job information.
        If not in slurm, return None
        TODO Refactor avoid saving intermediate file
        """
        # We proceeed
        sinfo_dict = {}
        try:
            job_id = os.environ['SLURM_JOB_ID']
        except KeyError:
            if self._warning == 0:
                LOGGER.debug('NOT STARTED FROM SLURM')
                self._warning += 1
            self.task_info = {}
            return

        # Read information from scontrol commend
        # Temporary file for storing output
        with tempfile.TemporaryFile(mode='w+') as tmp_file:
            subprocess.run('scontrol show jobid={:s}'.format(job_id),
                           shell=True,
                           check=True,
                           stdout=tmp_file)
            # Iterate through lines
            tmp_file.seek(0)
            for line in tmp_file:
                # Iterate through each pair
                for pair in line.split():
                    # Parse each pair
                    pair_s = pair.split('=')
                    sinfo_dict.update([(pair_s[0], pair_s[1])])
        type(self)._task_info = sinfo_dict
        self.task_info = sinfo_dict

    def get_end_time(self):
        """
        Query the end time of an job
        Return a datetime object
        """
        if self.task_info:
            end_time = datetime.strptime(self.task_info['EndTime'],
                                         '%Y-%m-%dT%H:%M:%S')
        else:
            end_time = None
        return end_time

    def get_remaining_seconds(self):
        """Return the remaining time in seconds"""
        return int((self.get_end_time() - datetime.now()).total_seconds())

    def get_n_cpus(self):
        """Return number of CPU allocated"""
        return self.task_info.get('NumCPUs', None)
