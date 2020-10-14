"""
Mapping AiiDA scheduler jobs to `Firework`
"""

from fireworks.user_objects.firetasks.script_task import ScriptTask
from fireworks.core.firework import Firework


class AiiDAJobFirework(Firework):
    """
    A Firework that encapsulate AiiDA jobs
    """

    def __init__(self, computer_id, 
                       remote_work_dir, aiida_job_id,
                       submit_script_name, 
                       mpinp, walltime,
                       stdout_fname, stderr_fname):
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
                'mpinp': mpinp, # Resources - used for job selection
                'walltime': walltime,   # in seconds
            },
            '_category': computer_id,   # Category - at least we have to enforce running on the intended computer!
            '_launch_dir': remote_work_dir,
        }

        script = f"chmod +x {submit_script_name} && ./{submit_script_name} > {stdout_fname} 2> {stderr_fname}"
        task = ScriptTask(script=script)

        return super().__init__(tasks=[task], spec=spec, name=f"aiida-{aiida_job_id}")


