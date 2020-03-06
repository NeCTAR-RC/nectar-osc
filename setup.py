#!/usr/bin/env python
# -*- coding: utf-8 -*-

#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:  # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError:  # for pip <= 9.0.3
    from pip.req import parse_requirements

requirements = parse_requirements("requirements.txt", session=False)

entry_points = {
    'openstack.cli.extension':
    ['nectar = nectar_osc.plugin', ],
    'openstack.nectar.v1':
    [
        'nectar security instance lock = nectar_osc.security:LockInstance',
        'nectar security instance unlock = nectar_osc.security:UnlockInstance',
        'nectar security instance delete = nectar_osc.security:DeleteInstance',
    ]
}


setup(
    name='nectar-osc',
    version='0.0.1',
    description=('OpenStack client plugin for misc Nectar tooling'),
    author='Adrian Smith',
    author_email='aussieade@gmail.com',
    url='https://github.com/NeCTAR-RC/nectar-osc',
    packages=[
        'nectar_osc',
    ],
    include_package_data=True,
    install_requires=[str(r.req) for r in requirements],
    license="Apache",
    zip_safe=False,
    classifiers=(
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
    ),
    entry_points=entry_points,
)
