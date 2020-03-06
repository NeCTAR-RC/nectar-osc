#!/usr/bin/env python
# -*- coding: utf-8 -*-


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements

requirements = parse_requirements("requirements.txt", session=False)

entry_points = {
    'openstack.cli.extension':
    ['nectar = nectar_osc.osc.plugin',],
    'openstack.nectar.v1':
    [
        'nectar security instance lock = nectar_osc.osc.security:LockInstance',
        'nectar security instance unlock = nectar_osc.osc.security:UnlockInstance',
        'nectar security instance delete = nectar_osc.osc.security:DeleteInstance',
    ]
}


setup(
    name='nectar-osc',
    version='0.0.1',
    description=('Client for misc Nectar tooling'),
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
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
    ),
    entry_points=entry_points,
)
