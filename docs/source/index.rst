.. figure:: images/AiiDA_transparent_logo.png
    :width: 250px
    :align: center

A plugin for launching jobs through `Fireworks`_ for `AiiDA`_
=============================================================

``aiida-fireworks-scheduler`` is available at http://github.com/zhubonan/aiida-fireworks-scheduler

By default, each AiiDA calculation is mapped to a single job that is submitted directly to the cluster. 
Sometimes, it may be useful to allow multiple AiiDA calculations to be run inside a single cluster job, for example:

  #. When there are limits on how many jobs a single user can have in the queue
  #. When typical workflows will need to run many small calculations sequentially - the overall queuing time can become significant.
  #. When calculations only require small amount of resources, but the user is forced to submit jobs of certain (larger) sizes.

This plugin allows AiiDA calculations to be performed with `fireworks`_, which is a workflow engine that focus on high-throughput execution using flexible computing resourcess.
Because the latter operates on a server-client mode, one must have a dedicated MongoDB server (*LaunchPad*) which must be accessible by both both the local and the remote computer.


How it works?
-------------

Below is a brief summary of the the life cycle of an AiiDA job:

  1. The job gets submitted.
  2. The daemon generate the input files and update them to the remote cluster.
  3. The daemon submit the jobs according to the submission script generated.
  4. The daemon monitors the jobs.
  5. When the job is finished, the outputs and then parsed locally.

Thanks to the entrypoint based plugin system implemented in AiiDA, most of these steps can be extended by a plugin.

Here, we alter steps 3 and step 4 - rather than submitting the job to the actual scheduler of the remote computer, it submits to the *LaunchPad* server.  
The *LaunchPad* server stores all *Firework* [#f1]_ to be run, as well as those that have finished.    
The same happens in in step 4 - rather than querying the actual scheduler periodically, the plugin pulls job states from the *LaunchPad* instead. 

Because now AiiDA merely registers jobs to the *LaunchPad* server, the user is now responsible for submitting actual jobs to the scheduler to run those *Firework* s. 

.. rubric:: Footnotes

.. [#f1] A *Firework* is like a *CalculationJob* in AiiDA - it runs some code using the computer. Here, it simply executes the original AiiDA submission script as if it is run in a cluster allocation. 

.. toctree::
   :maxdepth: 2

   user_guide/index
   developer_guide/index
   API documentation <apidoc/aiida_fireworks_scheduler>

If you use this plugin or if you use AiiDA for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  https://doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.

``aiida-fireworks-scheduler`` is released under the MIT license. 

Please contact zhubonan@outlook.com for information concerning ``aiida-fireworks-scheduler`` and the `AiiDA mailing list <http://www.aiida.net/mailing-list/>`_ for questions concerning ``aiida``.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _AiiDA: http://www.aiida.net
.. _Fireworks: https://materialsproject.github.io/fireworks/index.html
.. _fireworks: https://materialsproject.github.io/fireworks/index.html
.. _LaunchPad: https://materialsproject.github.io/fireworks/index.html


