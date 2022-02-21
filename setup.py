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

from setuptools import setup

from pbr.packaging import parse_requirements


entry_points = {
    'openstack.cli.extension':
    ['nectar = nectar_osc.plugin', ],
    'openstack.nectar.v1': [
        'nectar security instance lock = nectar_osc.security:LockInstance',
        'nectar security instance unlock = nectar_osc.security:UnlockInstance',
        'nectar security instance delete = nectar_osc.security:DeleteInstance',
        'nectar server show = nectar_osc.show:ShowInstance',
        'nectar server securitygroups = nectar_osc.show:ShowSecuritygroups',
        'nectar flavor list = nectar_osc.rating:ListFlavors',
    ],
    'oslo.config.opts': [
        'nectar_osc = nectar_osc.config:list_opts',
    ],
}


setup(
    name='nectar-osc',
    version='0.3.0',
    description=('OpenStack client plugin for misc Nectar tooling'),
    author='Adrian Smith',
    author_email='aussieade@gmail.com',
    url='https://github.com/NeCTAR-RC/nectar-osc',
    packages=[
        'nectar_osc',
    ],
    include_package_data=True,
    setup_requires=['pbr>=3.0.0'],
    install_requires=parse_requirements(),
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
