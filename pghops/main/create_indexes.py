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

"""Utility to create all indexes managed by pghops in parallel. See
the README for details."""

from pathlib import Path
import multiprocessing
import argparse
from pghops.main import props
from pghops.main import psql
from pghops.main import utils

INDEX_COMMAND = """
  select definition from pghops.index
  where
    enabled
    and table_name in
    (
      select table_schema || '.' || table_name
      from information_schema.tables
    );
"""

def get_index_statement_list(database):
    """Returns a list containing index creation statments from the table
pghops.index."""
    result = psql.call_psql('--dbname', database, '--command', INDEX_COMMAND,
                            '--tuples-only', '--echo-errors')
    stdout = result.stdout.strip()
    return stdout.split('\n')

def create_index(index_statement, database):
    """Calls psql to create the index."""
    try:
        utils.log_message('verbose', f"Running '{index_statement}'")
        result = psql.call_psql('--dbname', database, '--command', index_statement)
        if utils.get_verbosity() >= utils.to_verbosity('default'):
            print(result.stdout)
            print(result.stderr)
    except psql.PostgresError as error:
        if utils.get_verbosity() >= utils.to_verbosity('default'):
            print(error.stdout)
            print(error.stderr)
        raise RuntimeError(f'Error executing {index_statement} in database {database}. See above.')

def main(arg_list=None):
    """Main entrypoint into create index module."""
    # Create props and set parser. dbname and process_count
    args = PARSER.parse_args(arg_list)
    jobs = multiprocessing.cpu_count()
    if args.jobs:
        jobs = args.jobs
    props.load_initial_props(args)
    database = args.dbname
    cluster_directory = '.'
    if args.cluster_directory:
        cluster_directory = args.cluster_directory
    props.load_remaining_props(Path(cluster_directory), args.dbname, args)
    if props.get_prop('VERBOSITY'):
        utils.set_verbosity(props.get_prop('VERBOSITY'))
    index_statement_list = get_index_statement_list(database)
    # Create a list of iterables containing arguments for create_index
    # function.
    argument_lists = list(map(lambda x: (x, database), index_statement_list))
    with multiprocessing.Pool(jobs) as pool:
        pool.starmap(create_index, argument_lists)

PARSER = argparse.ArgumentParser(description="""Utility to create indexes managed by pghops.""")
PARSER.add_argument('dbname', help='Name of the database to connect to and create indexes for.')
PARSER.add_argument('-j', '--jobs', type=int,
                    help=('Number of parallel jobs to run when creating indexes. '
                          'Defaults to CPU count.'))
PARSER.add_argument('-c', '--cluster-directory',
                    help='A directory to search for additional properties to load.')
PARSER.add_argument(*props.PSQL_ARGUMENTS[0], help=props.PSQL_ARGUMENTS[1])
PARSER.add_argument(*props.PSQL_BASE_ARGUMENTS[0], help=props.PSQL_BASE_ARGUMENTS[1])
PARSER.add_argument(*props.DBCONNINFO[0], help=props.DBCONNINFO[1])
PARSER.add_argument(props.VERBOSITY[0], help=props.VERBOSITY[1],
                    choices=props.VERBOSITY_CHOICES)

if __name__ == '__main__':
    props.parser = PARSER
    main()
