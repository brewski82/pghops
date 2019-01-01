#!/bin/bash

set -e
set -u

parent_dir=$(dirname "$(dirname "$(readlink -f "$0")")")
cd "$parent_dir"

twine upload dist/*

echo "Upload done!"
