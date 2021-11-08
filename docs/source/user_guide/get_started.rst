===============
Getting started
===============

This plugin supplies an special scheduler that uses `fireworks`_ as the backend for job launching and placement, rather than the actual scheduler that is installed on the remote computer.
The main advantage of doing so is that task farming can be facilitated, e.g. a single scheduler jobs may run multiple AiiDA calculations in serial or in parallel. 
In addition, this also means that AiiDA calculations can be launched alongside those using `fireworks`_, and resources may be allocated dynamically based on priority of each jobs. 

.. note::

  Prerequisites:

  1. A working MongoDB server 
  2. Remote cluster is not *fenced*, e.g. the *compute nodes* have internet access at run time.
  3. Remote cluster's schedulers is one of the following:
    - SLURM
    - SGE
  4. Python environments are available on the remote cluster (typically through `conda` or `virtualenv`)
  
  The second one is not necessary if local arrangements can be made to for hosting the MongoDB server inside the firewall.
  Support of other schedulers can be implemented easily if you know how to fetch job time limit from inside a job.


Installation
++++++++++++

Use the following commands to install the plugin::

    git clone https://github.com/zhubonan/aiida-fireworks-scheduler
    cd aiida-fireworks-scheduler
    pip install -e .  # Note this will not install aiida, as you may need to do this on the remote machine!
    #pip install -e .[pre-commit,testing] # install extras for more features
    reentry scan -r aiida   # refresh the entry points
    verdi plugin list aiida.schedulers # should now show a scheduler entrypoint named `fw`



Setup for fireworks
+++++++++++++++++++

The plugin requires a working `fireworks`_ installation to work, please consult the `installation guide for fireworks`_ for this.
In particular, you will need to have an *LaunchPad* (the MongoDB server) up and running. 
The default *LaunchPad* will be used by the plugin.
You can check if your set up is working using the following command::

  lpad get_fws -m 1

Which should return exactly one *Firework* if there is any, or give an empty output. 

.. warning::
    Make sure you have *work though* the `basic tutorials`_ for Firework before continuing the setup process.
    In particular, you should be familiar with using `lpad` and `rlaunch` commands to manage and launch firework's
    workflows manually. Obviously, there is no need to learn how to deign fireworks workflows so you can skip those.

    Please confirm the following works:
    - `lpad get_fws` work on both *local* and *remote* computers.
    - `rlaunch` can be used to launch workflow on the *remote* computer. 

.. note::
    A MongoDB server is required to use this plugin, a source of free server is: https://www.mongodb.com/atlas/database.
    The server only stores a minimum amount of data and does not require lot of storage space, e.g. using the free-tier is usually fine.
    Alternatively, there are many VPS providers that offer pre-configured MongoDB instances.
    For the fireworks' tutorials, you can install MongoDB locally, it will not work for production calculations.
    This is because the server need to be reachable by both the local workstation (where AiiDA is installed) and the remote cluster. 
    If the remote cluster does not have internet access, then you will have to make certain arrangements, for example,
    using one of the post-processing node to host the MongoDB.


Setup for AiiDA 
+++++++++++++++

Once the plugin is installed, a ``fireworks`` scheduler will be made available to choose for a new ``Computer`` node. 
It is also possible to migrate existing ``Computer`` and associated ``Code`` nodes with a helper command::

  verdi data fireworks-scheduler duplicate-computer -Y <computer-name>  --included-codes

The new ``Computer`` will be assigned with a suffix ``-fw``, with original settings copied over, 


Running calculations
--------------------

On the local Computer
^^^^^^^^^^^^^^^^^^^^^

The process of launching jobs through ``fireworks`` is identical to those using the native schedulers. 
For ``resources`` single key ``tot_num_mpiprocs`` must be passed.
No other keys should be passed.
A few other options are supported:

  maximum_wallclock_seconds
    Specifies the maximum length of the jobs. The ``Firework`` that the AiiDA job corresponds to will only run if there is enough time left in the actual cluster job. 
    The AiiDA job will be terminated if it exceeds the wall clock limit.

  priority
    Specifies the priority of the underlying ``Firework`` (see `this page <https://materialsproject.github.io/fireworks/priority_tutorial.html>`_ for more) , those with higher priority will run first.
    AiiDA treats ``priority`` as a string so a string representation of the integer priority value can be passed. The default priority is ``'100'``.

On the remote Computer
^^^^^^^^^^^^^^^^^^^^^^

The `fireworks`_ launches jobs in a sightly indirect way - the submission script contains a line calling the ``rlaunch`` command that selects a ``Firework`` to run dynamically.
Job placement is controlled by the definition of *FireWorker*, which typically is provided as a yaml file.
Each ``Firework`` may have one of more *category* defined, and a *FireWorker* will only select those matches its own *category* list (see `here <https://materialsproject.github.io/fireworks/controlworker.html?highlight=category>`_ for more).
The plugin will handling assigning *category* of the underlying ``Firework`` for running the AiiDA job, but the user needs to manually point to right ``FwWork``.
The latter can be generated using a helper command::

  verdi data fireworks-scheduler generate-worker -Y <computer> --mpinp <tot_num_mpiprocs> myworker.yaml

.. note::

    Each *FireWorker* will only run jobs of a certain num of mpi processes.

Transfer the ``myworker.yaml`` to the remote computer, and use the following line in the job submission script:: 

    arlaunch -w myworker.yaml rapidfire

The ``arlaunch`` command is an enhanced version of the original ``rlaunch`` command provided by ``fireworks``, and it know the correct ``Fireworkk`` containing the AiiDA job to run.
To ensure that each ``Firework`` will have enough time to run as defined by the ``maximum_wallclock_seconds``, ``arlaunch`` must be able to query the time left from the acutal scheduler.
At the moment, only SGE and SLURM are supported, but it should be relatively easy to add support for other schedulers as well.


Example job script (SGE):

   .. code-block:: bash

    #!/bin/bash -l
    # Batch script to fireworks each with 24 mpi processes
    #$ -l h_rt=48:00:00
    #$ -l mem=4G
    #$ -l tmpfs=15G
    #$ -N aiida-fw-launcher

    # Select the MPI parallel environment and 16 processes.
    #$ -pe mpi 24

    # Set the working directory to the current directory
    #$ -cwd

    # Activate the conda environment where aiida-fireworks-scheduler is installed
    conda activate $HOME/Scratch/fireworks_env

    CMD="arlaunch -l $HOME/Scratch/fw-config/my_launchpad.yaml -w ./aiida-fworker-24core.yaml rapidfire"
    eval $CMD

Task-farming

   .. code-block:: bash

    #!/bin/bash -l
    # Batch script to fireworks each with 24 mpi processes
    #$ -l h_rt=48:00:00
    #$ -l mem=4G
    #$ -l tmpfs=15G
    #$ -N aiida-fw-launcher

    # Select the MPI parallel environment and 16 processes.
    #$ -pe mpi 24

    # Set the working directory to the current directory
    #$ -cwd

    # Activate the conda environment where aiida-fireworks-scheduler is installed
    conda activate $HOME/Scratch/fireworks_env

    # Launch 4 concurrent workers, each using 6-cores - only aiida jobs requesting 6 cores will be 
    # launched by these workers
    for i in $(seq 4); do
        arlaunch -l $HOME/Scratch/fw-config/my_launchpad.yaml -w ./aiida-fworker-6core.yaml rapidfire" &
    done
    wait

where ``aiida-fworker-24core.yaml`` is the *FireWorker* file. 

.. _fireworks: https://materialsproject.github.io/fireworks/
.. _installation guide for fireworks: https://materialsproject.github.io/fireworks/installation.html
.. _basic tutorials: https://materialsproject.github.io/fireworks/index.html#quickstart-and-tutorials