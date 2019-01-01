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

"""Handles the parsing and querying of all options to the pghops call.

Options can appear in property files, command line arguments, and
environment variables. Assuming <cluster-dir> is the direcotry
containing your projects sql, pghops loads options from the following
places, ordered from lowest to highest priority:

1. pghops/conf/default.properties
2. <cluster-dir>/pghops.properties
3. <cluster-dir>/<db>/pghops.properties
4. Environment variables
5. The file specified by the --options-file command line argument, if
   any
6. Command line arguments

pghops treats non command line options that only differ in case or
usage of underscore versus hyphen the same. For example:

wrap-all-in-transaction
wrap_all_in_transaction
Wrap_All_In_Transaction

all refer to the same option.

All .properties files must be in yaml format and contain only
associative arrays (key value pairs). See conf/default.properties for
an example.

Environment variables must be in all caps, use underscores, and have a
prefix of PGHOPS_. For example, the environment varaible for the
wrap-all-in-transaction property is PGHOPS_WRAP_ALL_IN_TRANSACTION.

"""
from pathlib import Path
import os
import argparse
import yaml
from .utils import get_resource_filename

PROPS = {}

def convert_bool(value):
    """Converts a variety of text inputs to a boolean value."""
    if value.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if value.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    raise argparse.ArgumentTypeError('Boolean value expected.')

def normalize_key(key, strip_prefix=False):
    """Use this function to normalize keys prior to adding to the PROPS
dictionary. Normalizing in this case means using a consistent format
for strings."""
    key = key.upper()
    key = key.replace('-', '_')
    if strip_prefix and key.startswith('PGHOPS_'):
        key = key.replace('PGHOPS_', '', 1)
    return key

def normalize_dict_keys(dictionary, omit_none=False, strip_prefix=False):
    """Given a dictionary, returns a new dictionary with normalized
keys."""
    normalize_dict = {}
    for key, value in dictionary.items():
        if value is not None or not omit_none:
            normalize_dict[normalize_key(key, strip_prefix=strip_prefix)] = value
    return normalize_dict

def load_yaml_file(file_path):
    """Loads a yaml file in the PROPS dictionary. The yaml file must only
contain a single associative array."""
    with open(file_path, 'r') as file:
        file_yaml = yaml.load(file)
        return PROPS.update(normalize_dict_keys(file_yaml))

def load_initial_props(args):
    """Loads the default properties and, if supplied, a file that should
contain a mapping of cluster directories."""
    # Add inital set of command line keys.
    PROPS.update(normalize_dict_keys(vars(args)))
    # Get the path to the default properties file.
    default_path = Path(get_resource_filename('conf/default.properties'))
    load_yaml_file(default_path)
    if 'PGHOPS_CLUSTER_MAP' in os.environ:
        load_yaml_file(os.environ['PGHOPS_CLUSTER_MAP'])
    if hasattr(args, 'cluster_map') and args.cluster_map:
        load_yaml_file(args.cluster_map)

def load_remaining_props(cluster_dir, db_name, args):
    """Loads any remaining properties."""
    path = cluster_dir / 'pghops.properties'
    if path.is_file():
        load_yaml_file(path)
    if db_name:
        path = cluster_dir / db_name / 'pghops.properties'
        if path.is_file():
            load_yaml_file(path)
    PROPS.update(normalize_dict_keys(os.environ, strip_prefix=True))
    if hasattr(args, 'OPTIONS_FILE'):
        load_yaml_file(args.OPTIONS_FILE)
    PROPS.update(normalize_dict_keys(vars(args), omit_none=True))
    return PROPS

def parse_args(arg_list=None):
    """Calls parse_args with the given arg_list or defaults to command
arguments."""
    if arg_list:
        return PARSER.parse_args(arg_list)
    return PARSER.parse_args()

def process_props(arg_list=None):
    """Loads all arguments from the command line and various properties
files into PROPS. Use arg_list to bypass the command line
arguments."""
    args = parse_args(arg_list)
    load_initial_props(args)
    # After loading the initial properties, check to see if the first
    # argument was a directory to cluster definitions or a name to
    # look up the directory in a cluster mapping file.
    cluster_directory = Path(args.cluster_directory)
    if cluster_directory.is_file():
        raise argparse.ArgumentTypeError('The first argument cluster_dir cannot be a file.')
    if not cluster_directory.is_dir():
        cluster_name = normalize_key(args.cluster_directory)
        if not cluster_name in PROPS:
            raise argparse.ArgumentTypeError(
                f'Unknown cluster name or non-existant directory: {cluster_name}')
        cluster_directory = Path(PROPS[cluster_name])
        # Now that we have the cluster directory, load the remaining
        # properties.
    args.cluster_directory = cluster_directory
    return load_remaining_props(cluster_directory, args.dbname, args)

def get_prop(prop):
    """Returns the given property of None. Only call this function after
loading all arguments and properties."""
    if prop in PROPS:
        return PROPS[prop]
    return None

DESCRIPTION = """pghops - Postgres Highly OPinionated migrationS.

See the README.md file for complete usage details.
"""
DBCONNINFO = (('--db-conninfo', '-C'),
              """psql argument - Alternative way to specify the connection parameters.""")
PSQL_ARGUMENTS = (('--psql-args', '-p'),
                  'A list of arguments to provide to psql, such as --host, --port, etc.')
PSQL_BASE_ARGUMENTS = (('--psql-base-args', '-b'),
                       '"Base" arguments to psql. Defaults to "--set ON_ERROR_STOP=1"')
TRANS_ALL = (('--wrap-all-in-transaction', '-a'),
             """Specify t (the default) to warp the entire migration in a single
transaction.""")
TRANS_EACH = (('--wrap-each-version-in-transaction', '-e'),
              """Specify t (default f) to wrap each individual version script in its
own transaction.""")
CLUSTER = ('cluster_directory', """The base directory containing your database sql. Defaults to the
current working directory. If you provide a cluster mapping file, pass
in the name of the cluster defined in that file instead.""")
DB = (('--dbname', '-d'), """By default pghops will migrate all dbs in the cluster
directory. Use this option to only update the specified db.""")
CLUSTER_MAP = (('--cluster-map', '-m'), """Path to a yaml file containing a map of cluster names to
directories. The cluster name can then be supplied as the first
argumentent instead of a directory.""")
FAIL_CONNECT = ('--fail-if-unable-to-connect',
                """Specify t (the default) to fail when unable to connect to the
Postgres server. Else stop silently.""")
FAIL_STANDBY = ('--fail-if-standby',
                """Specify t (the default) to fail if the Posgres server is in standby
mode. Else stop silently.""")
SAVE_SQL_TO_VERSION_TABLE = ('--save-sql-to-version-table',
                             """When true (the default), pghops saves all executed sql into the
column pghops.version.migration_sql. You may want to consider
disabling this feature if you have an extremely large amount of sql to
execute in your migration.""")
SAVE_INDEXES = ('--save-indexes',
                """When true, pghops scans the database directory for "create index"
and "create unique index" statements and saves them to the
pghops.index table. pghops does not create the indexes during the
migration, just saves them to the table so a different process can
create them asynchronously later.""")
DRY_RUN = ('--dry-run',
           'Do not execute the migration, only print the files that would have executed.')
VERBOSITY = ('--verbosity', """Verbosity level. One of default, verbose, or terse.
"terse" only prints errors. "verbose" echos all executed sql.""")
SUFFIXES = ('--script-suffixes', """A case-insensitive comma separated list of file suffixes that
migration files in the version direcotry must match in order to execute. Defaults to yml
and yaml""")
MIGRATION_FILE = ('--migration-file', """If you only want to execute a single migration file
instead of all in the versions directory, use this option. Include the suffix of the
file. pghops will not execute this file if the file has been executed
in the database before.""")
BOOL_CHOICES = [True, False]
VERBOSITY_CHOICES = ['verbose', 'default', 'terse']

PARSER = argparse.ArgumentParser(description=DESCRIPTION)
PARSER.add_argument(CLUSTER[0], help=CLUSTER[1], default=os.getcwd(), nargs='?')
PARSER.add_argument(*DB[0], help=DB[1])
PARSER.add_argument(*PSQL_ARGUMENTS[0], help=PSQL_ARGUMENTS[1])
PARSER.add_argument(*PSQL_BASE_ARGUMENTS[0], help=PSQL_BASE_ARGUMENTS[1])
PARSER.add_argument(*DBCONNINFO[0], help=DBCONNINFO[1])
PARSER.add_argument(*CLUSTER_MAP[0], help=CLUSTER_MAP[1])
PARSER.add_argument(*TRANS_ALL[0], help=TRANS_ALL[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(*TRANS_EACH[0], help=TRANS_EACH[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(FAIL_CONNECT[0], help=FAIL_CONNECT[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(FAIL_STANDBY[0], help=FAIL_STANDBY[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(SAVE_SQL_TO_VERSION_TABLE[0], help=SAVE_SQL_TO_VERSION_TABLE[1],
                    type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(SAVE_INDEXES[0], help=SAVE_INDEXES[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(DRY_RUN[0], help=DRY_RUN[1], type=convert_bool, choices=BOOL_CHOICES)
PARSER.add_argument(VERBOSITY[0], help=VERBOSITY[1], choices=VERBOSITY_CHOICES)
PARSER.add_argument(SUFFIXES[0], help=SUFFIXES[1])
PARSER.add_argument(MIGRATION_FILE[0], help=MIGRATION_FILE[1])

if __name__ == '__main__':
    ARGS = process_props(['/', '--h'])
    print(ARGS)
