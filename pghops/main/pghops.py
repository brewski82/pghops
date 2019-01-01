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

"""Main file for pghops."""
import os
import hashlib
import io
import re
from pathlib import Path
import yaml
from pghops.main import psql
from pghops.main.utils import to_verbosity, get_verbosity, set_verbosity, log_message, \
    make_temp_file, get_resource_filename
from pghops.main.props import get_prop, process_props

class Context:
    """Helper class used to hold various attributes used by each
function."""

    def __init__(self, cluster_directory):
        self.database = None
        self.cluster_directory = Path(cluster_directory)
        self.init_pghops_schema = None
        self.sql_file_path = None
        self.existing_schemas = None
        self.load_all_scripts = None
        self.existing_databases = []

    def load_existing_databases(self, connection_database):
        """Saves a list of all databases in the cluster."""
        if not self.existing_databases:
            self.existing_databases = psql.get_existing_database_list(connection_database)

    def does_database_exist(self):
        """Returns True if the database exists in the PG cluster."""
        return self.database in self.existing_databases


def call_psql(*args):
    """Call the PostgreSQL psql client with the supplied arguments only if
this is not a dry run."""
    if not get_prop('DRY_RUN'):
        result = psql.call_psql(*args)
        if get_verbosity() >= to_verbosity('default'):
            print(result.stdout)
            print(result.stderr)

def get_database_list(cluster_directory):
    """Returns the list of databases in the cluster directory to run
migrations for. If the --dbname option was provided, return that
database name. Else if a file named "databases" exists in the
directory, return the contents of the file. Else return the names of
each sub-directory in cluster_directory in alphabetical order.
"""
    if get_prop('DBNAME'):
        result = list()
        result.append(get_prop('DBNAME'))
        return  result
    database_file_path = cluster_directory / 'databases'
    if database_file_path.is_file():
        log_message('verbose', 'Getting database list from databases file.')
        with open(database_file_path) as database_file:
            databases = list(filter(lambda db: len(db.strip()) > 1,
                                    database_file.read().split('\n')))
    else:
        log_message('verbose', 'Getting database list from directory contents.')
        directory_contents = os.listdir(cluster_directory)
        databases = list(filter(lambda x: (cluster_directory / x).is_dir()
                                , directory_contents))
        databases.sort()
    log_message('verbose', f'Databases = {databases}')
    return databases

def ensure_database_exists(context):
    """Checks if the database exists. If the database does not exist, runs
the create_database.sql script located within the database
directory."""
    if not context.does_database_exist():
        create_database_file_path = context.cluster_directory / context.database \
            / 'create_database.sql'
        if not create_database_file_path.is_file():
            raise RuntimeError((f'Database {context.database} does not exist and '
                                f'database creation file {create_database_file_path} not found.'))
        log_message('default', (f'Database {context.database} does not exist. '
                                f'Creating it with {create_database_file_path}.'))
        call_psql('--file', str(create_database_file_path), '--dbname',
                  get_prop('CONNECTION_TEST_DATABASE'))

def get_local_script_list(context):
    """Returns a list of all version scripts in the local database
directory."""
    version_directory = context.cluster_directory / context.database / 'versions'
    if not version_directory.is_dir():
        raise RuntimeError(f'You must create directory {version_directory} before using pghops.')
    scripts = list()
    suffixes = get_prop('SCRIPT_SUFFIXES').split(',')
    single_script_to_execute = get_prop('MIGRATION_FILE')
    for script in version_directory.iterdir():
        if single_script_to_execute:
            if script.name == single_script_to_execute:
                scripts.append(script)
        elif script.suffix and script.suffix.lower() in suffixes:
            scripts.append(script)
    scripts.sort()
    return scripts

def find_file(context, directory, file):
    """Returns the path of the file on the system. Attempt to find the
file by trying the follwing in order, returning the first path that
exists:

1. context.cluster_directory / direcotry / file
2. context.cluster_directory / direcotry / file + .sql
3. context.cluster_directory / schemas / direcotry / file
4. context.cluster_directory / schemas / direcotry / file + .sql

Else raise error."""
    if directory.is_absolute():
        path = directory / file
        if not path.is_file():
            path = directory / (file + '.sql')
        if not path.is_file():
            raise RuntimeError(f'Unable to find {path}')
        return path.resolve(True)
    base_path = context.cluster_directory / context.database
    path = base_path / directory / file
    if not path.is_file():
        path = base_path / directory / (file + '.sql')
    if not path.is_file():
        path = base_path / 'schemas' / directory / file
    if not path.is_file():
        path = base_path / 'schemas' / directory / (file + '.sql')
    # Finally, if we are creating the initial pghops schema, load from
    # the pghops init directory.
    if not path.is_file() and context.init_pghops_schema:
        file_sql = file + '.sql'
        path = Path(get_resource_filename(f'init/schemas/{directory}/{file_sql}'))
    if not path.is_file():
        raise RuntimeError(f'Unable to find {base_path}/{directory}/{file}')
    return path.resolve(True)

def copy_sql_to_file(context, directory, file, string_io=None):
    """Copies the sql contained in FILE of DIRECTORY into
context.sql_file_path."""
    # Gather all sql and write to output file.
    file_path = find_file(context, directory, file)
    with open(file_path) as input_file:
        with open(context.sql_file_path, mode='a') as output_file:
            for line in input_file:
                output_file.write(line)
                if string_io:
                    string_io.write(line.replace("'", "''"))

def output_insert_version_record_sql(context, script_path, migration_sql):
    """Creates and outputs sql for inserting a new record into the pghops
version table."""
    file_name = script_path.name
    # Ensure file name is in correct format.
    if file_name.count('.') < 3:
        raise RuntimeError(f'Bad file name: {file_name} it must have at least three periods.')
    major, minor, patch, label = file_name.split('.')[:4]
    file_md5 = 'null'
    if not get_prop('SAVE_SQL_TO_VERSION_TABLE'):
        migration_sql = 'null::text'
    with open(script_path) as file:
        file_md5 = "'" + hashlib.md5(file.read().encode()).hexdigest() + "'"
    with open(context.sql_file_path, mode='a') as output_file:
        output_file.write(f"""insert into pghops.version
(
  major
  , minor
  , patch
  , label
  , file_name
  , file_md5
  , migration_sql
) values
(
  '{major}'
  , '{minor}'
  , '{patch}'
  , '{label}'
  , '{file_name}'
  , {file_md5}
  , {migration_sql}
);
"""
                          )

def load_version_script(context, script_path):
    """Loads the sql from the files pointed to by the provided version
script into context.sql_file_path. Then append sql to insert a new version
record. Optionally surround all sql in a transaction."""
    log_message('verbose', f'Loading {script_path}.')
    # Optionally output start of transaction.
    if get_prop('WRAP_EACH_VERSION_IN_TRANSACTION'):
        with open(context.sql_file_path, mode='a') as output_file:
            output_file.write('begin;\n')
    # Loop through the contents of the yaml version script. The keys
    # in the file are directories and the values are file names. For
    # each file, copy its contents into the temp sql
    # file. migration_sql is a String buffer to capture all of the sql
    # so we can later insert the contents into the version table.
    dictionary = None
    migration_sql = io.StringIO()
    migration_sql.write("'")
    with open(script_path) as file:
        dictionary = yaml.load(file)
    for directory, files in dictionary.items():
        if isinstance(files, list):
            for file in files:
                copy_sql_to_file(context, Path(directory), file, migration_sql)
        else:
            copy_sql_to_file(context, Path(directory), files, migration_sql)
    migration_sql.write("'")
    # Output the insert statement for the version table record.
    output_insert_version_record_sql(context, script_path, migration_sql.getvalue())
    # Optionally output end of transaction.
    if get_prop('WRAP_EACH_VERSION_IN_TRANSACTION'):
        with open(context.sql_file_path, mode='a') as output_file:
            output_file.write('commit;\n')

def ensure_pghops_schema_exists(context):
    """Checks if the schema "pghops" exists. If not, runs the inital
pghops setup scripts."""
    context.existing_schemas = psql.get_existing_schema_list(context.database)
    context.load_all_scripts = False
    if not 'pghops' in context.existing_schemas:
        pghops_version_script = \
            Path(get_resource_filename('init/versions/0000.0000.0000.pghops-init.yaml'))
        context.init_pghops_schema = True
        load_version_script(context, pghops_version_script)
        context.init_pghops_schema = False
        context.load_all_scripts = True

def collect_index_defintions(context):
    """Scans all sql files for index creation statements and returns them
in a list."""
    result = list()
    for path in list(Path(context.cluster_directory / context.database).rglob('*.[sS][qQ][lL]')):
        with open(path) as file:
            for line in file:
                if re.match(r'^create\W+(unique\W+)?index\W+if\W+not\W+exists\W+.+;',
                            line, re.IGNORECASE):
                    result.append(line.strip())
    return result

def extract_table_name_from_index_statement(index_statement):
    """Given an index creation statement, return the fully qualified table
name contained within the statement."""
    regex = (r'create\s+(unique\s+)?index\s+(concurrently\s+)?((if\s+not\s+exists\s+)?'
             r'[\w$]+\s+)?on\s+([\w$.]+)[\s(]+')
    match = re.search(regex, index_statement, re.IGNORECASE)
    if match:
        return match.group(5)
    return ''

def save_indexes(context):
    """Since creating new indexes on large tables can take considerable
time, sometimes we want to postpone index creation to run at a later
time rather than during a migration. pghops can optionally mananage
indexes by scanning the database directory for index creation
statements and saving those to the table pghops.index. Then a separate
process can loop through the table to create the indexes after the
migration."""
    index_statements = collect_index_defintions(context)
    if index_statements:
        tables = list(map(str.lower, psql.get_existing_table_list(context.database)))
        temp_file = make_temp_file('pghops-indexes-', '.sql')
        with open(temp_file, mode='a') as index_file:
            for index_statement in index_statements:
                table = extract_table_name_from_index_statement(index_statement)
                if table and table.lower() in tables:
                    sql = f"""insert into pghops.index
(
  table_name
  , definition
) values
(
  '{table}'
  , '{index_statement}'
) on conflict do nothing;
"""
                    index_file.write(sql)
        log_message('default', f'Adding new indexes collected in {temp_file} .')
        call_psql('--dbname', context.database, '--file', temp_file)
        os.remove(temp_file)

def migrate_database(context):
    """Runs migrations for a single database."""
    database = context.database
    log_message('default', f'Migrating database {database}')
    # Create a temp file to hold all the sql for this migration.
    context.sql_file_path = make_temp_file(f'pghops-{context.database}-')
    ensure_database_exists(context)
    # Optionally output begin transaction.
    if get_prop('WRAP_ALL_IN_TRANSACTION'):
        with open(context.sql_file_path, mode='a') as output_file:
            output_file.write('begin;\n')
    ensure_pghops_schema_exists(context)
    # Get list of scripts that need to be run.
    executed_scripts = list()
    if not context.load_all_scripts:
        executed_scripts = psql.get_executed_scripts_list(database)
    local_scripts = get_local_script_list(context)
    local_scripts_to_execute = list()
    for local_script in local_scripts:
        if not local_script.name in executed_scripts:
            local_scripts_to_execute.append(local_script)
    if local_scripts_to_execute:
        # Load each version script into the temp sql file.
        for script in local_scripts_to_execute:
            load_version_script(context, script)
            # Optionally output end transaction.
        if get_prop('WRAP_ALL_IN_TRANSACTION'):
            with open(context.sql_file_path, mode='a') as output_file:
                output_file.write('commit;\n')
        # Run the updates
        log_message('verbose', f'Executing sql in {context.sql_file_path} .')
        call_psql('--file', context.sql_file_path, '--dbname', context.database)
        # Save any indexes to the pghops index table.
    else:
        log_message('default', f'No new version scripts to apply for {database}.')
    save_indexes(context)
    log_message('default', f'Done migrating database {database}')

def migrate_cluster(context):
    """Runs migrations for all the databases in the given directory unless
a file named "databases" exist, in which case pghops will only run
migrations for databases listed in the file. cluster_directory should
be a Path object."""
    cluster_directory = context.cluster_directory
    log_message('default', f'Migrating cluster {cluster_directory}.')
    databases = get_database_list(cluster_directory)
    for database in databases:
        context.database = database
        migrate_database(context)
    log_message('default', 'Done all migrations.')

def main(arg_list=None):
    "Main entrypoint for pghops."
    process_props(arg_list)
    if get_prop('VERBOSITY'):
        set_verbosity(get_prop('VERBOSITY'))
    default_db = get_prop('CONNECTION_TEST_DATABASE')
    psql.test_connection(default_db)
    cluster_directory = Path(get_prop('CLUSTER_DIRECTORY'))
    context = Context(cluster_directory)
    context.load_existing_databases(default_db)
    migrate_cluster(context)

if __name__ == '__main__':
    main()
