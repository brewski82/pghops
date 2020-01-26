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
# pylint: disable=wrong-import-position

"""Functional tests that spin up a Postgres container to test all
aspects of pghops. You must have a docker compatible containerization
system and psql installed to run these tests.

Default is to start the Postgres container on port 5555. Adjust if
necessary. After starting we ping the server to ensure it is ready and
fail if unsuccessful after timeout_seconds. You may need to adjust
depending on your machine's performance.

"""
import os
import unittest
import sys
from pathlib import Path
from pghops.main import pghops
from pghops.main import psql
from pghops.main import create_indexes
from pghops.main import utils
from pghops.main.utils import make_temp_file

PORT = 5555
CONTAINER = 'pghops_postgres'
HOST = 'localhost'

CURRENT_DIRECTORY = Path(__file__).parent
CLUSTERS_DIRECTORY = CURRENT_DIRECTORY / 'test_clusters'
CLUSTER_A_DIRECTORY = CLUSTERS_DIRECTORY / 'cluster_a'
CLUSTER_A_V2_DIRECTORY = CLUSTERS_DIRECTORY / 'cluster_a_v2'
CLUSTER_A_V3_DIRECTORY = CLUSTERS_DIRECTORY / 'cluster_a_v3'
EXPECTED_RESULTS_DIRECTORY = CURRENT_DIRECTORY / 'expected_results' \
    / 'functional_tests'


def dump_and_compare(test, baseline_file_path):
    """Specifically for db_a3, dump data and compare with baseline
file."""
    temp_file = make_temp_file(baseline_file_path.stem, '.txt')
    with open(temp_file, mode='a') as output:
        result = psql.call_psql('--dbname', 'db_a3', '--command',
                                ('select version_id, major, minor, patch, label, file_name, '
                                 'file_md5, migration_sql, user_name, notes from '
                                 'pghops.version order by version_id;'),
                                '--expanded', '--echo-errors')
        output.write(result.stdout)
        result = psql.call_psql('--dbname', 'db_a3', '--command',
                                ('select index_id, table_name, definition, enabled, notes from '
                                 'pghops.index order by index_id'),
                                '--expanded', '--echo-errors')
        output.write(result.stdout)
        result = psql.call_psql('--dbname', 'db_a3', '--command',
                                ('select user_id, user_name '
                                 'from public.user order by user_id;'),
                                '--expanded', '--echo-errors')
        output.write(result.stdout)
        result = psql.call_psql('--dbname', 'db_a3', '--command',
                                ('select user_id, user_name '
                                 'from public.user_view order by user_id;'),
                                '--expanded', '--echo-errors')
        output.write(result.stdout)
    test.assertTrue(utils.compare_file_contents(baseline_file_path, temp_file))
    os.remove(temp_file)

class FunctionalTests(unittest.TestCase):
    """"Live" tests using a real PostgreSQL server."""

    def test_case_1(self):
        """Performs various migrations on a live PostgreSQL server."""
        psql_args = f'--port {PORT} --host {HOST} --username postgres'
        pghops.main([str(CLUSTER_A_DIRECTORY), '-p', psql_args])
        databases = psql.get_existing_database_list('postgres')
        self.assertTrue('db_a2' in databases)
        self.assertTrue('db_a3' in databases)
        self.assertTrue('db_a1' not in databases)
        dump_and_compare(self, EXPECTED_RESULTS_DIRECTORY / 'functional-test-db_a3-v1.txt')
        pghops.main([str(CLUSTER_A_V2_DIRECTORY), '-p', psql_args])
        dump_and_compare(self, EXPECTED_RESULTS_DIRECTORY / 'functional-test-db_a3-v2.txt')
        # Dry run should not produce any changes.
        pghops.main([str(CLUSTER_A_V3_DIRECTORY), '-p', psql_args, '--dry-run', 'true'])
        dump_and_compare(self, EXPECTED_RESULTS_DIRECTORY / 'functional-test-db_a3-v2.txt')
        # Ensure no errors occur during index creation.
        create_indexes.main(['db_a3', '-p', psql_args])

if __name__ == '__main__':
    if len(sys.argv) > 1:
        RUNTIME = sys.argv[1]
    else:
        RUNTIME = 'docker'
    utils.stop_postgres_container(RUNTIME, CONTAINER)
    utils.start_postgres_container(RUNTIME, CONTAINER, PORT, None)
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
