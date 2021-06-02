===============
Getting started
===============

This plugin supplies an special scheduler that uses `fireworks`_ as the backend for job launching and placement, rather than the actual scheduler that is installed on the remote computer.
The main advantage of doing so is that task farming can be facilitated, e.g. a single scheduler jobs may run multiple AiiDA calculations in serial or in parallel. 
In addition, this also means that AiiDA calculations can be launched alongside those using `fireworks`_, and resources may be allocated dynamically based on priority of each jobs. 


Installation
++++++++++++

Use the following commands to install the plugin::

    git clone https://github.com/zhubonan/aiida-fireworks-scheduler .
    cd aiida-fireworks-scheduler
    pip install -e .  # Note this will not install aiida, as you may need to do this on the remote machine!
    #pip install -e .[pre-commit,testing] # install extras for more features
    reentry scan -r aiida   # refresh the entry points
    verdi plugin list aiida.schedulers # should now show a scheduler entrypoint named `fw`


Usage
+++++

Computers using the ``fireworks`` scehduler must be created in the first place to use this plugin. 
This can be done by duplicating existing computers and selecting the ``fireworks`` scheduler when prompted.
Alternatively, existing ``Code`` and ``Computers`` using standard AiiDA scheduler may be migrated using the command ``verdi data fireworks-scheduler duplicate-computer``.

The plugin should also be installed on the remote computer. Each AiiDA job is identified with its ``Computer``'s hostname and the number of MPI processes to be launched.
During the run time, the jobs are selected by the Worker (see the `fireowrks`_ documentation for details), which is defined with a yaml file. These files may be generated 
using the command ``verdi data fireworks-scheduler generate-worker``. 

Jobs submitted can be launched with the following command on the remote computer within the job script submitted to the real scheduler::

    arlaunch -w <WORKER-name>.yaml rapidfire

This will select a job that it ready to run, change directly to the original folder uploaded by AiiDA and simply execuate the ``_aiidasubmit.sh`` job script.
The wallclock requested is respected during the job selection, only those requesting shorter run time than the time left for the job running `arlaunch` will be eligible to run.
However, this does mean that ``arlaunch`` (an enhanced verion of the ``rlaunch`` from ``fireworks``) must be able to get the time left from the real scheduelr.
At the moment, only SGE and SLURM are supported. But it should be easy to add more support for other scheduler should the user needs to.

.. _fireworks: https://materialsproject.github.io/fireworks/