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

"""Project util functions."""

import datetime
import tempfile
import subprocess
import time
import re
import pkg_resources

TIMEOUT_SECONDS = 10

class Verbosity():
    """Manages verbosity settings for log printing."""

    def __init__(self, verbosity=None):
        self._verbosity = to_verbosity('default')
        if verbosity:
            self.verbosity = verbosity

    @property
    def verbosity(self):
        "Returns the verbosity as an int."
        return self._verbosity

    @verbosity.setter
    def verbosity(self, value):
        "Sets verbosity. value can be a string or int."
        if isinstance(value, str):
            self._verbosity = to_verbosity(value)
        else:
            self._verbosity = value

    def reset_verbosity(self):
        "Resets verbosity to default"
        self.verbosity = to_verbosity('default')

def to_verbosity(string):
    """Converts the given verbosity to a number representing priority."""
    if string.lower().strip() == 'terse':
        return 1
    if string.lower().strip() == 'default':
        return 2
    if string.lower().strip() == 'verbose':
        return 3
    raise RuntimeError(f'Unknown verbosity level {string}.')

VERBOSITY = Verbosity('default')

def set_verbosity(verbosity):
    """Sets verbosity for printing log messages."""
    VERBOSITY.verbosity = verbosity

def get_verbosity():
    """Returns the current verbosity setting."""
    return VERBOSITY.verbosity

def print_message(message):
    """Prints a message to standard output, preceeded by a timestamp."""
    print('{}: {}'.format(datetime.datetime.now().isoformat(sep=' '), message))

def log_message(level, message):
    """Logs a message if the verbosity setting allows it."""
    if VERBOSITY.verbosity >= to_verbosity(level):
        print_message(message)

def make_temp_file(prefix, suffix=None):
    """Returns a path to a freshly created temp file."""
    path = tempfile.mkstemp(prefix=prefix, suffix=suffix)[1]
    return path

def get_resource_filename(resource):
    """Non-Python files in our package may be accessible only via the
ResourceManager API when importing from zip or Egg files. Use this
function to get a path to the resource file."""
    return pkg_resources.resource_filename('pghops', resource)

def test_postgres_container(port):
    """Pings the Postgres container to see if can accept commands."""
    args = ('psql', f'--host=localhost', f'--port={port}', '--dbname=postgres',
            '--user=postgres', '--command=select 1;')
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode == 0

def start_postgres_container(runtime, name, port, tag):
    """Starts the PostgreSQL container."""
    image = 'postgres'
    if tag:
        image = f'{image}:{tag}'
    args = (runtime, 'run', '--detach=true', '--rm=true', f'--publish={port}:5432',
            f'--name={name}', image)
    print_message(f'Starting Postgres {name} {image}.')
    call = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if call.returncode != 0:
        raise RuntimeError(call.stderr)
    # Loop until startup finishes.
    i = 0
    while not test_postgres_container(port):
        time.sleep(1)
        i = i + 1
        if i > TIMEOUT_SECONDS:
            raise RuntimeError('Unable to connect to postgres server.')
    print_message(f'Done starting postgres {name}.')
    return call

def stop_postgres_container(runtime, name):
    """Stops the PostgreSQL container."""
    args = (runtime, 'kill', name)
    # For convenience we will ignore errors if the container does not
    # exists.
    print_message(f'Stopping Postgres {name}.')
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        # If we succeeded in killing the container, wait a moment so
        # we can re-use the container name.
        time.sleep(2)

def compare_file_contents(file_path_a, file_path_b, ignore_whitespace=True):
    """Compare the contents of two files, optionally ignoring
whitespace."""
    contents_a = ''
    with open(file_path_a) as file_a:
        contents_a = file_a.read()
    contents_b = ''
    with open(file_path_b) as file_b:
        contents_b = file_b.read()
    if ignore_whitespace:
        contents_a = re.sub(r'\s', '', contents_a)
        contents_b = re.sub(r'\s', '', contents_b)
    return contents_a == contents_b
