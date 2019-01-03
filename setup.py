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

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pghops",
    version="1.0.2",
    author="William Bruschi",
    author_email="william.bruschi@gmail.com",
    description="A highly opionated Postgresql migration tool",
    license='GPLv3',
    keywords='PostgreSQL database migrations',
    install_requires=['PyYAML'],
    entry_points={
        'console_scripts': [
            'pghops = pghops.main.pghops:main',
            'create_indexes = pghops.main.create_indexes:main',
        ]
    },
    python_requires='>=3.7',
    test_suite='pghops.tests.unit_tests',
    include_package_data=True,
    package_data={
        '': ['init/schemas/pghops/tables/*.sql', 'init/schemas/pghops/*.sql',
             'conf/default.properties', 'init/versions/*.yaml']
    },
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/brewski82/pghops",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent"
    ]
)
