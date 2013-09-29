#!/usr/bin/env python3

from setuptools import setup

setup(
    name='modes',
    version='0.1',
    license='MIT License',
    author='td',
    description='SSR Mode-S decoding tools',
    install_requires=['bitstring'],
    packages=['modes'],
    tests_require=['nose'],
    test_suite='nose.collector'
)
