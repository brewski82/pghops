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
#
# pylint: disable=wrong-import-position,too-many-statements

"""pghops unit tests."""
import sys
import os
import unittest
import argparse
import tempfile
import filecmp
from pathlib import Path
from pghops.main import props
from pghops.main import pghops
from pghops.main import psql
from pghops.main import utils

CURRENT_DIRECTORY = Path(__file__).parent
CLUSTERS_DIRECTORY = CURRENT_DIRECTORY / 'test_clusters'
CLUSTER_A_DIRECTORY = CLUSTERS_DIRECTORY / 'cluster_a'
CLUSTER_B_DIRECTORY = CLUSTERS_DIRECTORY / 'cluster_b'
EXPECTED_RESULTS_DIRECTORY = CURRENT_DIRECTORY / 'expected_results' / 'unit_tests'
utils.set_verbosity('verbose')

class TestUtils(unittest.TestCase):
    """Tests for pghops utils module."""

    def test_log(self):
        """Test logging with different verbosity settings."""
        utils.set_verbosity('default')
        stdout = sys.stdout
        temp_file = utils.make_temp_file('pghops-log-test-', '.txt')
        # Since we log time stamps, we will simply test we get the
        # expected number of lines in each file.
        with open(temp_file, 'w') as file:
            sys.stdout = file
            utils.log_message('default', 'default message')
        with open(temp_file) as file:
            self.assertEqual(1, sum(1 for line in file))
        with open(temp_file, 'w') as file:
            sys.stdout = file
            utils.log_message('default', 'default message')
            utils.log_message('terse', 'terse message')
            utils.log_message('verbose', 'verbose message')
        with open(temp_file) as file:
            self.assertEqual(2, sum(1 for line in file))
        utils.set_verbosity('verbose')
        with open(temp_file, 'w') as file:
            sys.stdout = file
            utils.log_message('default', 'default message')
            utils.log_message('terse', 'terse message')
            utils.log_message('verbose', 'verbose message')
        with open(temp_file) as file:
            self.assertEqual(3, sum(1 for line in file))
        utils.set_verbosity('terse')
        with open(temp_file, 'w') as file:
            sys.stdout = file
            utils.log_message('default', 'default message')
            utils.log_message('terse', 'terse message')
            utils.log_message('verbose', 'verbose message')
        with open(temp_file) as file:
            self.assertEqual(1, sum(1 for line in file))
        utils.set_verbosity('default')
        with open(temp_file, 'w') as file:
            sys.stdout = file
            utils.log_message('default', 'default message')
            utils.log_message('terse', 'terse message')
            utils.log_message('verbose', 'verbose message')
        with open(temp_file) as file:
            self.assertEqual(2, sum(1 for line in file))
        sys.stdout = stdout
        os.remove(temp_file)
        with self.assertRaises(RuntimeError):
            utils.set_verbosity('bad')
        utils.set_verbosity('verbose')

class TestPsql(unittest.TestCase):
    """Tests for psql module."""

    def test_test_connection(self):
        """Tests that connection failures fail gracefully."""
        # Do not rely on an active Postgres server for unit
        # tests. Thus just test connection failures.
        props.process_props([str(CLUSTER_A_DIRECTORY)])
        with self.assertRaises(RuntimeError):
            psql.test_connection('non-existent-db')
        props.process_props([str(CLUSTER_A_DIRECTORY), '--fail-if-unable-to-connect', 'false'])
        with self.assertRaises(SystemExit):
            psql.test_connection('non-existent-db')

    def test_get_base_connection_args(self):
        """Tests that pghops correctly applies base connection arguments for
psql calls."""
        props.process_props([str(CLUSTER_A_DIRECTORY), '-p', '--host testhost --port testport'])
        args = psql.get_base_connection_args()
        self.assertEqual(args, ('psql', '--host', 'testhost', '--port',
                                'testport', '--set', 'ON_ERROR_STOP=1'))
        props.process_props([str(CLUSTER_A_DIRECTORY), '--db-conninfo', 'testconninfo'])
        args = psql.get_base_connection_args()
        self.assertEqual(args, ('psql', 'testconninfo', '--set', 'ON_ERROR_STOP=1'))
        props.process_props([str(CLUSTER_A_DIRECTORY), '-p',
                             '--host testhost --port testport', '-b', ''])
        args = psql.get_base_connection_args()
        self.assertEqual(args, ('psql', '--host', 'testhost', '--port', 'testport'))
        props.process_props([str(CLUSTER_A_DIRECTORY), '-p', '--host testhost --port testport',
                             '-b', '--set ON_ERROR_STOP=2'])
        args = psql.get_base_connection_args()
        self.assertEqual(args, ('psql', '--host', 'testhost', '--port', 'testport',
                                '--set', 'ON_ERROR_STOP=2'))

class TestProps(unittest.TestCase):
    """Tests for pghops module."""

    def test_normalize(self):
        """Tests that property keys are properly formatted."""
        self.assertEqual(props.normalize_key('FOO'), 'FOO')
        self.assertEqual(props.normalize_key('Abc'), 'ABC')
        self.assertEqual(props.normalize_key('Abc-Def'), 'ABC_DEF')
        self.assertEqual(props.normalize_key('Abc_Def'), 'ABC_DEF')

    def test_normalized_dict(self):
        """Tests that property keys are properly formatted."""
        dictionary = {'abc': 1, 'd-e': 2, 'f_g': 3}
        normalize_dict = props.normalize_dict_keys(dictionary)
        self.assertTrue('ABC' in normalize_dict)
        self.assertTrue('D_E' in normalize_dict)
        self.assertTrue('F_G' in normalize_dict)
        self.assertTrue('abc' not in normalize_dict)
        self.assertTrue('d-e' not in normalize_dict)
        self.assertTrue('f-g' not in normalize_dict)

    def test_load_props(self):
        """Test prop loading priority."""
        parser = argparse.ArgumentParser()
        parser.add_argument('-foo', dest='FOO')
        args = parser.parse_args(['-foo', 'bar'])
        props.load_initial_props(args)
        props.load_remaining_props(Path(tempfile.gettempdir()), 'db', args)
        self.assertEqual(props.PROPS['FOO'], 'bar')
        self.assertTrue(props.PROPS['WRAP_ALL_IN_TRANSACTION'])
        self.assertFalse(props.PROPS['WRAP_EACH_VERSION_IN_TRANSACTION'])
        parser.add_argument('--wrap-all-in-transaction',
                            dest='WRAP_ALL_IN_TRANSACTION', type=props.convert_bool)
        args = parser.parse_args(['--wrap-all-in-transaction', 'false'])
        props.load_remaining_props(Path(tempfile.gettempdir()), 'db', args)
        self.assertFalse(props.PROPS['WRAP_ALL_IN_TRANSACTION'])

    def test_process_props(self):
        """Tests that property loading works correctly."""
        with self.assertRaises(argparse.ArgumentTypeError):
            props.process_props([__file__])
        with self.assertRaises(argparse.ArgumentTypeError):
            props.process_props(['nonexistingprop'])
        # Test using cluster mapping file.
        cluster_map_path = CLUSTERS_DIRECTORY / 'pghopstest'
        props.process_props(['clustername', '--cluster-map', str(cluster_map_path)])
        self.assertEqual(str(props.PROPS['CLUSTER_DIRECTORY']), '/tmp')

class TestPghops(unittest.TestCase):
    """ Tests the main pghops module."""

    def test_get_database_list(self):
        """Tests that pghops finds all the databases in the given cluster
directory."""
        database_a_list = pghops.get_database_list(CLUSTER_A_DIRECTORY)
        self.assertEqual(database_a_list, ['db_a2', 'db_a3'])
        database_b_list = pghops.get_database_list(CLUSTER_B_DIRECTORY)
        self.assertEqual(database_b_list, ['db_1', 'db_2'])
        props.process_props([str(CLUSTER_A_DIRECTORY), '--dbname', 'otherdb'])
        database_other_list = pghops.get_database_list(CLUSTER_B_DIRECTORY)
        self.assertEqual(database_other_list, ['otherdb'])

    def test_migrate_database(self):
        """Tests that pghops errors when trying to migrate a database that
does not exist in the cluster directory."""
        with self.assertRaises(RuntimeError):
            context = pghops.Context(CLUSTER_A_DIRECTORY)
            context.database = 'non-existing-db'
            pghops.migrate_database(context)

    def test_load_version_script(self):
        """Tests that pghops writes corrects sql when loading a migration
script."""
        temp_file = utils.make_temp_file('pghops-unit-test-load-version-script', '.sql')
        context = pghops.Context(CLUSTER_A_DIRECTORY)
        context.sql_file_path = Path(temp_file)
        context.database = 'db_a3'
        pghops.load_version_script(context, CLUSTER_A_DIRECTORY / 'db_a3' / 'versions' / \
                                   '0000.0001.0000.init.yml')
        expected_path = EXPECTED_RESULTS_DIRECTORY / 'expected-test_load_version_script.sql'
        self.assertTrue(filecmp.cmp(temp_file, expected_path, False))
        os.remove(temp_file)

    def test_get_local_script_list(self):
        """Tests the pghops can find and return all the migration files in the
cluster directory."""
        context = pghops.Context(Path(CLUSTER_A_DIRECTORY) / 'script_list_test')
        context.database = 'test1'
        scripts = pghops.get_local_script_list(context)
        self.assertEqual(0, len(scripts))
        context.database = 'test2'
        scripts = pghops.get_local_script_list(context)
        self.assertEqual(0, len(scripts))
        context.database = 'test3'
        scripts = pghops.get_local_script_list(context)
        self.assertEqual(4, len(scripts))
        script_names = list()
        for script in scripts:
            script_names.append(script.name)
        self.assertEqual(['1.yml', '2.yaml', '3.YML', '4.YAML'], script_names)
        props.process_props([str(CLUSTER_A_DIRECTORY), '--migration-file', '2.yaml'])
        scripts = pghops.get_local_script_list(context)
        self.assertEqual(1, len(scripts))
        script_names = list()
        for script in scripts:
            script_names.append(script.name)
        self.assertEqual(['2.yaml'], script_names)


    def test_output_insert_version_record_sql(self):
        """Tests the process that creates the sql statement for adding a new
record to the pghops.version table."""
        context = pghops.Context(CLUSTER_A_DIRECTORY)
        context.database = 'db_a3'
        temp_file = utils.make_temp_file('pghops-unit-test-insert-version-record', '.sql')
        context.sql_file_path = temp_file
        script_path = context.cluster_directory / context.database / 'versions' / \
            '0000.0001.0000.init.yml'
        migration_sql = """'create table public.user (
  user_id serial primary key
  , user_name text
);

create index if not exists public_user_user_name_index on public.user(user_name);
create or replace view public.user_view as
select * from public.user;
select 1;
select 2;
select ''hi'' as x;
'"""
        props.process_props([str(CLUSTER_A_DIRECTORY)])
        pghops.output_insert_version_record_sql(context, script_path, migration_sql)
        expected_file_path = EXPECTED_RESULTS_DIRECTORY / 'expected-migration-sql.sql'
        self.assertTrue(filecmp.cmp(temp_file, expected_file_path, False))
        os.remove(temp_file)
        script_path = context.cluster_directory / context.database / 'versions' / 'badfilename.yml'
        # Test bad file name format.
        with self.assertRaises(RuntimeError):
            pghops.output_insert_version_record_sql(context, script_path, migration_sql)

    def test_ensure_pghops_schema_exists(self):
        """Ensure pghops can find init scripts outside of the target database
directory."""
        context = pghops.Context(CLUSTER_A_DIRECTORY)
        context.database = 'db_a3'
        context.init_pghops_schema = True
        temp_file = utils.make_temp_file('pghops-unit-test-init-version-script', '.sql')
        context.sql_file_path = temp_file
        pghops_version_script = \
            Path(utils.get_resource_filename('init/versions/0000.0000.0000.pghops-init.yaml'))
        props.process_props([str(CLUSTER_A_DIRECTORY)])
        pghops.load_version_script(context, pghops_version_script)
        expected_file_path = EXPECTED_RESULTS_DIRECTORY / 'expected-init-schema.sql'
        self.assertTrue(filecmp.cmp(temp_file, expected_file_path, False))
        os.remove(temp_file)

    def test_collect_index_defintions(self):
        """Tests finding all create index statements in a cluster
directory."""
        context = pghops.Context(CLUSTER_A_DIRECTORY)
        context.database = 'db_a1'
        indexes = pghops.collect_index_defintions(context)
        print(indexes)
        expected_result = [
            'create index if not exists test_index_1 on testing(x);'
            , 'create UNIQUE index if not exists test_index_3 on testing(x);'
            , 'create UNIQUE index if not exists test_index_4 on customschema.testing(x);'
        ]
        self.assertEqual(indexes, expected_result)

    def test_extract_table_name_from_index_statement(self):
        """Tests finding the fully qualified table name from various create
index statements."""
        sql = 'create index on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create index x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique index on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique index x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create index concurrently on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create INDEX CONCURRENTLY x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique  index concurrently on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique index concurrently x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create index if not exists x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique index if not exists x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create index concurrently if not exists x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create unique index concurrently if not exists  x on test (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'test')
        sql = 'create index on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create index x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create unique index on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'CREATE UNIQUE index x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create index concurrently on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create index concurrently x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create unique  index concurrently on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create unique index concurrently x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create index if not exists x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create unique index if not exists x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create index concurrently if not exists x on schema.table(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'schema.table')
        sql = 'create unique index concurrently if not exists  x on sch12$$ema.ta$$2ble(x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 'sch12$$ema.ta$$2ble')
        sql = ('create unique index concurrently if not  '
               'exists x_$_name_ on s_ch12$$ema_.t_a$$2ble(x);')
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, 's_ch12$$ema_.t_a$$2ble')
        sql = ('create unique index concurrently if not  exists '
               '__x_$_name_ on __s_ch12$$ema_.__t_a$$2ble(x);')
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, '__s_ch12$$ema_.__t_a$$2ble')
        sql = 'create unique index concurrently if not  exists __x_$_name_ on __t_a$$2ble (x);'
        result = pghops.extract_table_name_from_index_statement(sql)
        self.assertEqual(result, '__t_a$$2ble')

if __name__ == '__main__':
    unittest.main()
