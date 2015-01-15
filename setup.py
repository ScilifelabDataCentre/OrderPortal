#!/usr/bin/env python

from setuptools import setup

setup(name='OrderPortal',
      version='0.1',
      description='A portal for orders (aka. requests, project applications) to a facility from its users.',
      license='MIT',
      author='Per Kraulis',
      author_email='per.kraulis@scilifelab.se',
      url='https://github.com/pekrau/OrderPortal',
      packages=['orderportal'],
      package_dir={'orderportal': 'orderportal'},
      include_package_data=True,
      install_requires=['tornado>=4.0',
                        'couchdb>=0.8',
                        'pyyaml>=3.10'],
     )
