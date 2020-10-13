"""
Specialised transport for running jobs
"""

from aiida.transports.plugins.ssh import SshTransport


class ProxyTransport(SshTransport):
    """
    A specialised transport that traps the command execution related to job submission.
    To be used in conjuction with FwScheduler
    """
    pass