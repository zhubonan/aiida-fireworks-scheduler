"""
Mapping AiiDA scheduler jobs to `Firework`
"""

from string import Template
from fireworks.user_objects.firetasks.script_task import ScriptTask
from fireworks.core.firework import Firework
from aiida_fireworks_scheduler.common import RESERVED_CATEGORY

# Here the goal is to run the script in an environment as close to that will be used by
# the actual scheduler as possible.

# Here the command assumes that the runtime environment sources the .bashrc, e.g. it is a login shell.
# This is known to be untrue the case for SLURM, but here we still want to have this behaviour
# well defined.

RUN_SCRIPT_TEMPLATE = Template(r"""
printf "\ntouch .FINISHED" >> ${submit_script_name}
chmod +x ${submit_script_name}

timeout ${walltime_seconds}s env -i HOME=$$HOME bash -l ./${submit_script_name} > ${stdout_fname} 2> ${stderr_fname} & 
sleep 1
chmod -x ${submit_script_name}

while [[ -e /proc/$$! ]]; do
    if [[ -e AIIDA_STOP ]]; then
       kill $$!
       exit 11
    fi
    sleep 5
done

if [ ! -f .FINISHED ]; then
    echo Script timed out
    exit 12
else
    rm .FINISHED
fi

echo ALL DONE
""")


class AiiDAJobFirework(Firework):
    """
    A Firework that encapsulate AiiDA jobs
    """
    def __init__(  # pylint: disable=too-many-arguments
            self,
            computer_id,
            username,
            remote_work_dir,
            job_name,
            submit_script_name,
            mpinp,
            walltime,
            stdout_fname,
            stderr_fname,
            priority=100):
        """
        Instantiate a Firework to run jobs prepared by AiiDA daemon on the remote
        computer
        """
        spec = {
            '_aiida_job_info': {
                'computer_id': computer_id,
                'username': username,
                'remote_work_dir': remote_work_dir,
                'submit_script_name': submit_script_name,
                'mpinp': mpinp,  # Resources - used for job selection
                'walltime': walltime,  # in seconds
            },
            # Category set it to a special values to indicate it is an AiiDA job
            '_category': RESERVED_CATEGORY,
            '_launch_dir': remote_work_dir,
            '_priority': priority,
        }

        script = RUN_SCRIPT_TEMPLATE.substitute(
            submit_script_name=submit_script_name,
            walltime_seconds=walltime,
            stdout_fname=stdout_fname,
            stderr_fname=stderr_fname)
        task = ScriptTask(script=script,
                          shell_exe='/bin/bash',
                          fizzle_bad_rc=False,
                          defuse_bad_rc=False)

        super().__init__(tasks=[task], spec=spec, name=job_name)
