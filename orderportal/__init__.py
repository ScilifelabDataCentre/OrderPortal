"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '0.3'

# Default settings, to be changed in a settings YAML file.
settings = dict(BASE_URL='http://localhost:8885/',
                DB_SERVER='http://localhost:5984/',
                REGISTRATION_ENABLED=True,
                TORNADO_DEBUG=True,
                LOGGING_DEBUG=True,
                LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
                ORDER_STATUS_FILENAME='{ROOT}/data/order_status.yaml',
                SITE_NAME='OrderPortal',
                UNIVERSITY_LIST_FILENAME='{ROOT}/data/university_list.yaml',
                )
