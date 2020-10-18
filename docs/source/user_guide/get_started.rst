===============
Getting started
===============

This page should contain a short guide on what the plugin does and
a short example on how to use the plugin.

Installation
++++++++++++

Use the following commands to install the plugin::

    git clone https://github.com/zhubonan/aiida-fireengine .
    cd aiida-fireengine
    pip install -e .  # Note this will not install aiida, as you may need to do this on the remote machine!
    #pip install -e .[pre-commit,testing] # install extras for more features
    verdi plugin list aiida.schedulers # should now show a scheduler entrypoint named `fw`


Usage
+++++