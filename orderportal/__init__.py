"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '0.2'

# Default settings, to be changed in a settings YAML file.
settings = dict(BASE_URL='http://localhost:8885/',
                DB_SERVER='http://localhost:5984/',
                REGISTRATION_ENABLED=True,
                TORNADO_DEBUG=True,
                LOGGING_DEBUG=True,
                LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
                FACILITY_NAME='[facility]',
                ORDER_STATUS_FILENAME='{ROOT}/order_status.yaml',
                UNIVERSITY_LIST_FILENAME='{ROOT}/university_list.yaml',
                )
