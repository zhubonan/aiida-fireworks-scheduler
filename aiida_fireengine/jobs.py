"""
Mapping AiiDA scheduler jobs to `Firework`
"""

from string import Template
from fireworks.user_objects.firetasks.script_task import ScriptTask
from fireworks.core.firework import Firework
from aiida_fireengine.common import RESERVED_CATEGORY

RUN_SCRIPT_TEMPLATE = Template("""
chmod +x ${submit_script_name}

timeout ${walltime_seconds}s ./${submit_script_name} > ${stdout_fname} 2> ${stderr_fname} & 
sleep 1
chmod -x ${submit_script_name}

while [[ -e /proc/$$! ]]; do
    if [[ -e AIIDA_STOP ]]; then
       kill $$!
       exit 11
    fi
    sleep 5
done
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
        task = ScriptTask(script=script, shell_exe='/bin/bash')

        super().__init__(tasks=[task], spec=spec, name=job_name)
