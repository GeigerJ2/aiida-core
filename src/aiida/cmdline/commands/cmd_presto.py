###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""``verdi presto`` command."""

from __future__ import annotations

import pathlib
import re
import typing as t

import click

from aiida.cmdline.commands.cmd_verdi import verdi
from aiida.cmdline.utils import echo
from aiida.cmdline.params import options
from aiida.manage.configuration import get_config_option

DEFAULT_PROFILE_NAME_PREFIX: str = 'presto'


def get_default_presto_profile_name():
    from aiida.manage import get_config

    profile_names = get_config().profile_names
    indices = []

    for profile_name in profile_names:
        if match := re.search(r'presto[-]?(\d+)?', profile_name):
            indices.append(int(match.group(1) or '0'))

    if not indices:
        return DEFAULT_PROFILE_NAME_PREFIX

    last_index = int(sorted(indices)[-1])

    return f'{DEFAULT_PROFILE_NAME_PREFIX}-{last_index + 1}'


def _postgres_from_profile_name(
    profile_name: str,
    non_interactive: bool,
    database_hostname: str = 'localhost',
    database_port: int = 5432,
) -> dict[str, t.Any]:
    """Generate a default PostgreSQL user and db based on the profile name.

    Only the database hostname and port can be specified, while the remaining config options are derived from the
    profile name.

    """

    import secrets

    from aiida.manage.configuration.settings import AIIDA_CONFIG_FOLDER
    from aiida.manage.external.postgres import Postgres

    database_name = f'aiida-{profile_name}'
    database_username = f'aiida-{profile_name}'
    database_password = secrets.token_hex(15)

    try:
        postgres = Postgres(interactive=not non_interactive, quiet=False)
        database_username, database_name = postgres.create_dbuser_db_safe(
            dbname=database_name, dbuser=database_username, dbpass=database_password
        )
    except Exception as exception:
        echo.echo_critical(f'Unable to automatically create the PostgreSQL user and database: {exception}')

    return {
        'database_hostname': database_hostname,
        'database_port': database_port,
        'database_name': database_name,
        'database_username': database_username,
        'database_password': database_password,
        'repository_uri': f'file://{AIIDA_CONFIG_FOLDER / "repository" / profile_name}',
    }


@verdi.command('presto')
@click.option(
    '--profile-name',
    default=lambda: get_default_presto_profile_name(),
    show_default=True,
    help=f'Name of the profile. By default, a unique name starting with `{DEFAULT_PROFILE_NAME_PREFIX}` is automatically generated.',
)
@click.option(
    '--email',
    default=lambda: get_config_option('autofill.user.email') or 'aiida@localhost',
    show_default=True,
    help='Email of the default user.',
)
@click.option(
    '--use-postgres',
    is_flag=True,
    help=('When toggled on, the profile uses a PostgreSQL database instead of an SQLite one. The command attempts to automatically create a user and database to use for the profile, but this can fail depending on the configuration of the server. If it fails or you want to specify custom options, use ``verdi profile setup core.psql_dos`` instead.',)
)
@options.NON_INTERACTIVE(help='Never prompt, such as for sudo password.')
@click.pass_context
def verdi_presto(ctx, profile_name, email, use_postgres, non_interactive):
    """Set up a new profile in a jiffy.

    This command aims to make setting up a new profile as easy as possible. It does not require any services, such as
    PostgreSQL and RabbitMQ. It intentionally provides only a limited amount of options to customize the profile and by
    default does not require any options to be specified at all. To create a new profile with full control over its
    configuration, please use `verdi profile setup` instead.

    After running `verdi presto` you can immediately start using AiiDA without additional setup. The command performs
    the following actions:

    \b
    * Create a new profile that is set as the new default
    * Create a default user for the profile (email can be configured through the `--email` option)
    * Set up the localhost as a `Computer` and configure it
    * Set a number of configuration options with sensible defaults

    By default the command creates a profile that uses SQLite for the database. It automatically checks for RabbitMQ
    running on the localhost, and, if it can connect, configures that as the broker for the profile. Otherwise, the
    profile is created without a broker, in which case some functionality will be unavailable, most notably running the
    daemon and submitting processes to said daemon.

    When the `--use-postgres` flag is toggled, the command tries to automatically create a PostgreSQL user and database.
    If successful, the newly created profile uses this PostgreSQL database instead of SQLite.
    """

    from aiida.brokers.rabbitmq.defaults import detect_rabbitmq_config
    from aiida.common import exceptions
    from aiida.manage.configuration import create_profile, load_profile
    from aiida.orm import Computer

    storage_config: dict[str, t.Any] = (
        _postgres_from_profile_name(profile_name=profile_name, non_interactive=non_interactive) if use_postgres else {}
    )
    storage_backend = 'core.psql_dos' if use_postgres else 'core.sqlite_dos'

    if use_postgres:
        echo.echo_report(
            '`--use-postgres` enabled and database creation successful: configuring the profile to use PostgreSQL.'
        )
    else:
        echo.echo_report('Option `--use-postgres` not enabled: configuring the profile to use SQLite.')

    broker_config = detect_rabbitmq_config()
    broker_backend = 'core.rabbitmq' if broker_config is not None else None

    if broker_config is None:
        echo.echo_report('RabbitMQ server not found: configuring the profile without a broker.')
    else:
        echo.echo_report('RabbitMQ server detected: configuring the profile with a broker.')

    try:
        profile = create_profile(
            ctx.obj.config,
            name=profile_name,
            email=email,
            storage_backend=storage_backend,
            storage_config=storage_config,
            broker_backend=broker_backend,
            broker_config=broker_config,
        )
    except (ValueError, TypeError, exceptions.EntryPointError, exceptions.StorageMigrationError) as exception:
        echo.echo_critical(str(exception))

    echo.echo_success(f'Created new profile `{profile.name}`.')

    ctx.obj.config.set_option('runner.poll.interval', 1, scope=profile.name)
    ctx.obj.config.set_default_profile(profile.name, overwrite=True)
    ctx.obj.config.store()

    load_profile(profile.name, allow_switch=True)
    echo.echo_info(f'Loaded newly created profile `{profile.name}`.')

    filepath_scratch = pathlib.Path(ctx.obj.config.dirpath) / 'scratch' / profile.name

    computer = Computer(
        label='localhost',
        hostname='localhost',
        description='Localhost automatically created by `verdi presto`',
        transport_type='core.local',
        scheduler_type='core.direct',
        workdir=str(filepath_scratch),
    ).store()
    computer.configure(safe_interval=0)
    computer.set_minimum_job_poll_interval(1)
    computer.set_default_mpiprocs_per_machine(1)

    echo.echo_success('Configured the localhost as a computer.')
