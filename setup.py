#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='OrderPortal',
      version='2.0',
      description='A portal for orders (aka. requests, project applications) to a facility from its users.',
      license='MIT',
      author='Per Kraulis',
      author_email='per.kraulis@scilifelab.se',
      url='https://github.com/pekrau/OrderPortal',
      packages = find_packages(),
      include_package_data=True,
      install_requires=['tornado',
                        'CouchDB',
                        'pyyaml',
                        'markdown'],
     )
