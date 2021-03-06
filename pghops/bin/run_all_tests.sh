#!/bin/bash

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

################################################################################
#
# Runs pghops tests
#
################################################################################

set -e
set -u
set -o pipefail

runtime="${1:-docker}"

base_dir=$(dirname $(dirname $(dirname $(readlink -f "$0"))))

cd $base_dir

python3 -m pghops.tests.unit_tests
python3 -m pghops.tests.functional_tests "$runtime"

echo
echo "Tests succeeded!"
echo
