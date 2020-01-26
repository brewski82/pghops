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

"""Framework for running unit tests against a PostgreSQL db."""

import os
import argparse
import re
import sys
import subprocess
from pathlib import Path
from pghops.main import props
from pghops.main import pghops
from pghops.main import utils
from pghops.main import psql

ARGS = []

PARSER = argparse.ArgumentParser(description="""Unit testing framework for PostgreSQL.""")
PARSER.add_argument('command', help=("The command to run. 'run' runs the "
                                     "test(s). 'generate' creates or refreshes"
                                     " baseline files for the tests.")
                    , choices=['run', 'generate'])
PARSER.add_argument('test', help=('When specified, only run the supplied test. '
                                  'You can either provide a test suite or a '
                                  'specific test within a suite such as '
                                  '<suite>/<test>.'), default=None, nargs='?')
PARSER.add_argument('-c', '--cluster-directory', default=os.getcwd(),
                    help=('The source code directory for your PostgreSQL cluster. '
                          'Defaults to the current working directory.'))
PARSER.add_argument('--dbname', '-d', help=('When specified, only run tests '
                                            'for the supplied database.'))
PARSER.add_argument('--container-tag', help=('The PostgreSQL container image tag to '
                                             'use. If omitted, uses latest.'))
PARSER.add_argument('--container-runtime', help=('The container runtime to use. '
                                                 'Defaults to docker.'))
PARSER.add_argument('--container-port', help=('The PostgreSQL container to expose.'
                                              ' Defaults to 5555. If you change '
                                              'this also change the port in the '
                                              'psql args.'))
PARSER.add_argument('--container-name',
                    help=('The PostgreSQL container name to use. '
                          'Defaults to pghops-postgresql.'))
PARSER.add_argument('--skip-container-shutdown',
                    help=('When true, do not shutdown the container container '
                          'after running tests. Helpful when developing tests '
                          'and running migrations takes some time. After the '
                          'initial run, you can run or develop individual tests '
                          'without having to perform a complete migration.')
                    , type=props.convert_bool, choices=props.BOOL_CHOICES)
PARSER.add_argument('--ignore-whitespace',
                    help=('Whether or not to ignore whitespace when comparing '
                          'files. Defaults to true.')
                    , type=props.convert_bool, choices=props.BOOL_CHOICES)
PARSER.add_argument(*props.PSQL_BASE_ARGUMENTS[0],
                    help=('"Base" arguments to psql. Defaults to "--port=5555 '
                          '--host=localhost --username=postgres --echo-all '
                          '--no-psqlrc --set=SHOW_CONTEXT=never"'))
PARSER.add_argument('--psql-base-migration-args',
                    help=('Base arguments to psql when running migrations. '
                          'Typically when you run the migration you want to '
                          'fail if encountering an error, which may not be '
                          'the case when running the tests. Defaults to '
                          '--port=5555 --host=localhost --username=postgres '
                          '--echo-all --no-psqlrc --set ON_ERROR_STOP=1'))
PARSER.add_argument(*props.PSQL_ARGUMENTS[0],
                    help='A list of additional arguments to provide to psql.')
PARSER.add_argument(*props.DBCONNINFO[0], help=props.DBCONNINFO[1])
PARSER.add_argument(props.VERBOSITY[0], help=props.VERBOSITY[1],
                    choices=props.VERBOSITY_CHOICES)
PARSER.add_argument(props.SUFFIXES[0], help=props.SUFFIXES[1])
PARSER.add_argument(props.OPTIONS_FILE[0], help=props.OPTIONS_FILE[1])

class TestError(Exception):
    "Exception thrown by the pghops test module."

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __str__(self):
        return self.message

def get_suite_path(cluster_directory, database, sub_directory):
    "Returns a path object of the test suite directory."
    path = cluster_directory / database / 'tests'
    if sub_directory:
        path = path / sub_directory
    return path

def is_test_file(path):
    "Returns true if the file at path is a unit test file."
    if path.is_dir():
        return False
    name = path.name
    if re.match(r'.*test\.sql$', name, re.IGNORECASE):
        return True
    return False

def get_test_suite_sql_file_list(cluster_directory, database, sub_directory, where=None):
    "Return a list of test files to execute."
    result = list()
    path = get_suite_path(cluster_directory, database, sub_directory)
    if where:
        path = path / where
        if path.is_file():
            result.append(path.name)
            return result
    if not path.is_dir():
        return result
    for file in path.iterdir():
        if is_test_file(file):
            result.append(file.name)
    result.sort()
    return result

def stop_container():
    "Stops the PostgreSQL container."
    name = props.get_prop('CONTAINER_NAME')
    runtime = props.get_prop('CONTAINER_RUNTIME')
    do_shutdown = not props.get_prop('SKIP_CONTAINER_SHUTDOWN')
    if do_shutdown:
        utils.stop_postgres_container(runtime, name)

def launch_container():
    "Runs the PostgreSQL container image."
    runtime = props.get_prop('CONTAINER_RUNTIME')
    name = props.get_prop('CONTAINER_NAME')
    port = props.get_prop('CONTAINER_PORT')
    tag = props.get_prop('CONTAINER_TAG')
    is_running = True
    try:
        psql.test_connection(props.get_prop('CONNECTION_TEST_DATABASE'))
    except RuntimeError:
        is_running = False
    if not is_running or not props.get_prop('SKIP_CONTAINER_SHUTDOWN'):
        stop_container()
        utils.start_postgres_container(runtime, name, port, tag)

def run_pghops():
    "Runs pghops migrations on the container PostgreSQL image."
    pghops.main()

def calculate_expected_file_name(test_file_name):
    "Returns the name of the expected file name."
    return re.sub('test.sql$', 'expected.txt', test_file_name, 1, re.IGNORECASE)

def compare_result(expected_path, psql_result, test_name):
    "Compares the results of the test to the file containg expected results."
    ignore_whitespace = props.get_prop('IGNORE_WHITESPACE')
    if not expected_path.is_file():
        raise TestError(f'Expected file {expected_path} not found!')
    temp_file = utils.make_temp_file(expected_path.stem, '.txt')
    with open(temp_file, mode='w') as output:
        output.write(psql_result.stdout)
    is_equal = utils.compare_file_contents(
        expected_path, temp_file, ignore_whitespace)
    if not is_equal:
        raise TestError(f"""Files not equal:
Expected file: {expected_path}
Actual file:   {temp_file}
""")
    utils.log_message('default', f'Test {test_name} passed.')
    os.remove(temp_file)

def generate_expected(expected_path, psql_result, test_name):
    "Generates the file containing the expected results for future test runs."
    with open(expected_path, mode='w') as output:
        output.write(psql_result.stdout)
    utils.log_message('default', f'Generated {test_name} expected file.')

def call_psql(file_path, database):
    """Calls psql for the provided database and with input from the
contents of file_path. We avoid using psql.call_psql in this case
because in the event of an error an absolute path to the file
containing the error is printed by psql, which would make our expected
files host specific."""
    args = psql.get_base_connection_args() + ('--dbname', database)
    contents = ''
    with open(file_path) as file_contents:
        contents = file_contents.read()
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, input=contents)
    if result.returncode != 0:
        raise psql.PostgresError(result.returncode, result.stdout, result.stderr)
    return result

def run_test_suite(fun, cluster_directory, database, sub_directory, where=None):
    """Runs all the test files in the provided test suite. The test suite
is all the tests found in the directory by appending database / tests
/ sub_directory to the cluster directory. If where is provided, only
run the tests that match the filter."""
    path = get_suite_path(cluster_directory, database, sub_directory)
    utils.log_message('verbose', f'Checking for tests in {path}')
    test_files = get_test_suite_sql_file_list(
        cluster_directory,
        database,
        sub_directory,
        where)
    if not test_files:
        return
    if where:
        path = path / where
        if path.is_file():
            path = path.parent
    load_props(path)
    utils.log_message('default', f'Looping through tests in {path}')
    launch_container()
    # When running the migration, we want to stop on any error, but
    # when we run tests, we want to continue on errors. Thus, for the
    # migration only, set the stop on error flag.
    orginal_args = props.get_prop('PSQL_BASE_ARGS')
    props.PROPS['PSQL_BASE_ARGS'] = props.get_prop('PSQL_BASE_MIGRATION_ARGS')
    pghops.run_migration()
    props.PROPS['PSQL_BASE_ARGS'] = orginal_args
    for file in test_files:
        file_path = path / file
        expected_file_name = calculate_expected_file_name(file)
        expected_path = path / expected_file_name
        result = call_psql(file_path, database)
        fun(expected_path, result, file)
    stop_container()

def get_test_suite_directories(directory):
    "Returns a sorted list of directory names in the supplied directory."
    directories = list()
    for sub_directory in directory.iterdir():
        if sub_directory.is_dir():
            directories.append(sub_directory.name)
    directories.sort()
    return directories

def test_database(fun, cluster_directory, database, where):
    "Run the PostgreSQL tests for a database."
    test_directory = get_suite_path(cluster_directory, database, None)
    utils.log_message('verbose',
                      f'Checking for suite directory {test_directory}')
    if not test_directory.is_dir():
        return
    # Tests can be stored in one or more sub-directories or parent
    # 'tests' directory. Run the sub-directories first.
    suite_directories = get_test_suite_directories(test_directory)
    utils.log_message('verbose',
                      f'Test suite sub directories = {suite_directories}')
    for suite_directory in suite_directories:
        run_test_suite(fun, cluster_directory, database, suite_directory, where)
    # Run tests in parent directory
    run_test_suite(fun, cluster_directory, database, None, where)

def run_tests(fun):
    "Run the PostgreSQL tests for the cluster."
    # Get the list of databases to run tests for. This takes into
    # consideration the --dbname argument.
    cluster_directory = Path(props.get_prop('CLUSTER_DIRECTORY'))
    where = props.get_prop('TEST')
    database_list = pghops.get_database_list(cluster_directory)
    for database in database_list:
        test_database(fun, cluster_directory, database, where)

def load_props(directory):
    "Searches for and loads property files in the given directory."
    prop_file = directory / 'pghops-test.properties'
    if prop_file.is_file():
        props.load_yaml_file(prop_file)
    # Re-load environment variables
    props.PROPS.update(props.normalize_dict_keys(os.environ, strip_prefix=True))
    # Load props from options file, if any.
    args = ARGS[0]
    if hasattr(args, 'OPTIONS_FILE'):
        props.load_yaml_file(args.OPTIONS_FILE)
    # Load command line options
    props.PROPS.update(props.normalize_dict_keys(vars(args), omit_none=True))
    # Set verbosity
    if props.get_prop('VERBOSITY'):
        utils.set_verbosity(props.get_prop('VERBOSITY'))


def main(arg_list=None):
    """Main entry point into unit testing framework."""
    try:
        args = PARSER.parse_args(arg_list)
        ARGS.append(args)
        props.load_initial_props(args)
        cluster_directory = Path(args.cluster_directory)
        props.load_remaining_props(cluster_directory, args.dbname, args)
        # For the test framework, load default properties from a different
        # default file.
        props.load_yaml_file(Path(utils.get_resource_filename('conf/default-test.properties')))
        load_props(cluster_directory)
        # The only difference between running tests and generating
        # expected files is the function to use once we start looping
        # through the tests. Determine the function to use in the loop
        # here and pass it down the chain.
        if args.command == 'run':
            utils.log_message('verbose', 'Running tests.')
            run_tests(compare_result)
            utils.log_message('default', 'All tests passed!')
        if args.command == 'generate':
            utils.log_message('verbose', 'Generated expected files.')
            run_tests(generate_expected)
            utils.log_message('default', 'Done generating expected files!')
    except TestError as err:
        sys.exit(str(err))

if __name__ == '__main__':
    main()
