# Copyright 2019 William Bruschi - williambruschi.net
#
# This file is part of pghops.
#
# pghops is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pghops is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pghops.  If not, see <https://www.gnu.org/licenses/>.

"""A module for interacting with psql, the PostgreSQL client."""
import subprocess
import sys
import re
from .props import get_prop
from .utils import log_message

class PostgresError(Exception):
    """Exceptions for calls to PostgreSQL."""
    def __init__(self, returncode, stdout, stderr):
        Exception.__init__(self)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        return (f'Call to Postgres server returned non-zero exit code {self.returncode}. '
                f'stdout = {self.stdout}. stderr = {self.stderr}.')

def subprocess_run(args):
    """Wrapper around subprocess.run."""
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def call_psql(*args):
    """Executes the Postgres client psql with the provided arguments."""
    args = get_base_connection_args() + args
    result = subprocess_run(args)
    if result.returncode != 0:
        raise PostgresError(result.returncode, result.stdout, result.stderr)
    return result

def strip_quotes(string):
    """Remove both single and doulbe quotes from the beginning and ending
of given string."""
    result = string.strip('"')
    return result.strip("'")

def get_base_connection_args():
    """Creates an arg tuple suitable for arguments psql. Determines
arguments from those passed to pghops."""
    args = ('psql',)
    if get_prop('DB_CONNINFO'):
        args = args + (get_prop('DB_CONNINFO'),)
    if get_prop('PSQL_ARGS'):
        arg_list = list(filter(lambda x: len(x.strip()) > 1, get_prop('PSQL_ARGS').split(' ')))
        arg_list = list(map(strip_quotes, arg_list))
        args = args + tuple(arg_list)
    if get_prop('PSQL_BASE_ARGS'):
        arg_list = list(filter(lambda x: len(x.strip()) > 1, get_prop('PSQL_BASE_ARGS').split(' ')))
        arg_list = list(map(strip_quotes, arg_list))
        args = args + tuple(arg_list)
    return args

def test_connection(dbname):
    """Ensure we can connect to the target Postgres server and, if we can
connect, that the server is not in recovery/standby mode."""
    args = get_base_connection_args()
    args = args + ('--dbname', dbname)
    log_message('verbose', f'Testing connection to database {dbname} using psql arguments {args}.')
    result = subprocess_run(args + ('--command', 'select 1'))
    if result.returncode != 0:
        if get_prop('FAIL_IF_UNABLE_TO_CONNECT'):
            raise RuntimeError(f'Connection test to {dbname} failed')
        else:
            log_message('default', f'Unable to connect to {dbname}. Exiting.')
            sys.exit()
    log_message('verbose', f'Connection successful. Checking if in standby mode.')
    result = subprocess_run(args + ('--tuples-only', '--command',
                                    'select pg_is_in_recovery()', '--echo-errors'))
    is_in_recovery = re.sub(r'\W', '', result.stdout)
    if is_in_recovery != 'f':
        if get_prop('FAIL_IF_STANDBY'):
            raise RuntimeError((f'Connection test to {dbname} failed -'
                                ' server in standby/recovery mode.'))
        else:
            log_message('default', f'{dbname} appears to be in standby/recovery mode. Exiting.')
            sys.exit()

def get_existing_database_list(dbname):
    """Get a list of existing databases from the Postgres server."""
    result = call_psql('--command', 'select datname from pg_database where not datistemplate;',
                       '--tuples-only', '--dbname', dbname, '--echo-errors')
    stdout = result.stdout.strip()
    return re.sub('\\n', '', stdout).split(' ')

def get_existing_schema_list(dbname):
    """Returns a list of schemas that exist on the database."""
    result = call_psql('--command', 'select nspname from pg_namespace', '--tuples-only',
                       '--dbname', dbname, '--echo-errors')
    stdout = result.stdout.strip()
    return re.sub('\\n', '', stdout).split(' ')

def get_existing_table_list(dbname):
    """Returns a list of fully qualified table names that exist on the
database."""
    result = call_psql('--tuples-only', '--dbname', dbname, '--echo-errors', '--command',
                       "select table_schema || '.' || table_name from information_schema.tables;")
    stdout = result.stdout.strip()
    return re.sub('\\n', '', stdout).split(' ')

def get_executed_scripts_list(dbname):
    """Returns a list of script names that were executed on this
database. The pghops.version table tracks these file names."""
    result = call_psql('--command', 'select file_name from pghops.version order by file_name;',
                       '--tuples-only', '--dbname', dbname, '--echo-errors')
    stdout = result.stdout.strip()
    return re.sub('\\n', '', stdout).split(' ')

if __name__ == '__main__':
    test_connection('postgres')
