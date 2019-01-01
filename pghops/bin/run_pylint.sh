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
# along with Foobar.  If not, see <https://www.gnu.org/licenses/>.

################################################################################
#
# Runs pylint3 on every file in the project.
#
################################################################################

set -e
set -u
set -o pipefail

base_dir=$(dirname $(dirname $(readlink -f "$0")))

function call_pylint() {
    local file="$1"
    echo "File = $file"
    pylint-3 --init-hook="import sys; sys.path.append('${base_dir}/main')" "$file"
}

function call_pylint_for_directory() {
    local directory="$1"
    for file in $(ls -v "$base_dir/$directory/"*py); do
        call_pylint "$file"
    done
}

call_pylint_for_directory "main"
call_pylint_for_directory "tests"

echo
echo "Code is clean!"
echo
