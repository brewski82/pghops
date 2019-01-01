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
import pkg_resources

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
