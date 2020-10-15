"""
Mapping AiiDA scheduler jobs to `Firework`
"""

from fireworks import explicit_serialize
from fireworks.user_objects.firetasks.script_task import ScriptTask
from fireworks.core.firework import Firework, FireTaskBase
from string import Template

RUN_SCRIPT_TEMPLATE = Template("""
chmod +x ${submit_script_name}

./${submit_script_name} > ${stdout_fname} 2> ${stderr_fname} & 

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
    def __init__(self, computer_id, remote_work_dir, job_name,
                 submit_script_name, mpinp, walltime, stdout_fname,
                 stderr_fname):
        """
        Instantiate a Firework to run jobs prepared by AiiDA daemon on the remote 
        computer
        
        Arguments
        """
        spec = {
            '_aiida_job_info': {
                'computer_id': computer_id,
                'remote_work_dir': remote_work_dir,
                'submit_script_name': submit_script_name,
                'mpinp': mpinp,  # Resources - used for job selection
                'walltime': walltime,  # in seconds
            },
            '_category':
            computer_id,  # Category - at least we have to enforce running on the intended computer!
            '_launch_dir': remote_work_dir,
        }

        script = RUN_SCRIPT_TEMPLATE.substitute(
            submit_script_name=submit_script_name,
            stdout_fname=stdout_fname,
            stderr_fname=stderr_fname)
        task = ScriptTask(script=script, shell_exe='/bin/bash')

        return super().__init__(tasks=[task], spec=spec, name=job_name)
