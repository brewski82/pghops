#!/bin/bash

set -e
set -u

parent_dir=$(dirname "$(dirname "$(readlink -f "$0")")")
cd "$parent_dir"

if [ -e "build" ]; then
    rm -rf build
fi

if [ -e "dist" ]; then
    rm -rf dist
fi

if [ -e "pghops.egg-info" ]; then
    rm -rf pghops.egg-info
fi

python3 setup.py sdist bdist_wheel

echo "Build done!"
