"""
Convenient tools for operations
"""
from copy import deepcopy

import click

import aiida.cmdline.utils.echo as echo
from aiida.cmdline.utils.decorators import with_dbenv
from aiida.cmdline.params import options
from aiida.cmdline.commands.cmd_data import verdi_data

from .fwscheduler import DEFAULT_USERNAME
from .fworker import AiiDAFWorker

# pylint: disable=import-outside-toplevel,no-member


@verdi_data.group("fireengine")
def fe_cli():
    """Command line interface for aiida-fireengine"""
@fe_cli.command("duplicate-computer")
@options.COMPUTER()
@options.INPUT_PLUGIN()
@click.option('--include-codes',
              is_flag=True,
              default=False,
              help='Wether migrate Codes as well.')
@click.option('--suffix', default="fw", help='Suffix for the new computer')
@options.DRY_RUN()
@with_dbenv()
def duplicate_fe(computer, include_codes, input_plugin, suffix, dry_run):
    """
    Create copies of the existing computer using FwScheduler, add existing
    Code if requested.
    """
    from aiida import orm
    from aiida.orm.utils.builders.computer import ComputerBuilder

    builder = ComputerBuilder.from_computer(computer)
    builder.scheduler = "fireworks"
    builder.label += "-" + suffix
    builder.description += "(Using Fireworks as the scheduler.)"
    comp = builder.new()
    echo.echo_info(f"Adding new computer {comp}")
    if not dry_run:
        comp.store()
        echo.echo_info(f"Computer {comp} has been saved to the database")

    if include_codes:
        qb_code_filters = dict()
        if input_plugin:
            qb_code_filters['attributes.input_plugin'] = input_plugin.name

        user = orm.User.objects.get_default()
        qbd = orm.QueryBuilder()
        qbd.append(orm.Computer, tag='computer', filters={'id': computer.pk})
        qbd.append(orm.Code,
                   with_computer='computer',
                   tag='code',
                   filters=qb_code_filters,
                   project=['*'])
        qbd.append(orm.User,
                   tag='user',
                   with_node='code',
                   filters={'email': user.email})
        new_codes = []
        for (code, ) in qbd.iterall():
            new_code = deepcopy(code)
            new_code.set_remote_computer_exec(
                (comp, code.get_remote_exec_path()))
            new_codes.append(new_code)
            echo.echo_info(f"Adding new code {new_code}")

        if not dry_run:
            for code in new_codes:
                code.store()
                echo.echo_info(f"Code {code} has been saved to the database")

    if dry_run:
        echo.echo_info("This is a dry-run nothing has been saved.")


@fe_cli.command("generate-worker")
@options.COMPUTER()
@click.option("--mpinp", type=int, help="Number of MPI processes.")
@click.option("--name", type=str, help="Name of the worker.")
@click.option("--category",
              type=str,
              multiple=True,
              help="Categories of the NON-AIIDA jobs for the worker to run.")
@click.argument('output_file')
def generate_worker(computer, mpinp, name, output_file, category):
    """Generate worker fire for a particular computer"""

    if computer.scheduler_type != "fireworks":
        echo.echo_critical(
            "Can only generate worker for computer using 'fireworks' scheduler."
        )
        return

    hostname = computer.hostname
    config = computer.get_configuration()
    username = config.get('username', DEFAULT_USERNAME)

    if name is None:
        name = f"Worker on {hostname} for {username} with mpinp: {mpinp}"

    worker = AiiDAFWorker(computer_id=hostname,
                          mpinp=mpinp,
                          username=username,
                          name=name,
                          category=category)
    worker.to_file(output_file)
