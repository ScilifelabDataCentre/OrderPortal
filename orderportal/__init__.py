"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '0.5'

# Default settings, to be changed in a settings YAML file.
settings = dict(SITE_NAME='OrderPortal',
                BASE_URL='http://localhost:8885/',
                DB_SERVER='http://localhost:5984/',
                REGISTRATION_ENABLED=True,
                TORNADO_DEBUG=True,
                LOGGING_DEBUG=True,
                LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
                ORDER_STATUSES_FILENAME='{ROOT}/data/order_statuses.yaml',
                ORDER_TRANSITIONS_FILENAME='{ROOT}/data/order_transitions.yaml',
                LOGIN_MAX_AGE_DAYS=7,
                UNIVERSITIES_FILENAME='{ROOT}/data/university_list.yaml',
                SENDLIST = {'account':
                                {'status':
                                     {'enabled': ['owner']},
                                 'edit': ['owner'],
                                 'reset': ['owner'],
                                 'password': ['owner']
                                 }
                            },
                )
