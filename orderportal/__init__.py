"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '0.7'

# Default settings, may be changed in a settings YAML file.
settings = dict(SITE_DIR='{ROOT}/generic',
                SITE_NAME='OrderPortal',
                BASE_URL='http://localhost:8885/',
                DB_SERVER='http://localhost:5984/',
                TORNADO_DEBUG=False,
                LOGGING_DEBUG=False,
                LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
                LOGIN_MAX_AGE_DAYS=6,
                INITIAL_TEXTS_FILEPATH='{SITE_DIR}/initial_texts.yaml',
                ACCOUNT_MESSAGES_FILEPATH='{SITE_DIR}/account_messages.yaml',
                ORDER_STATUSES_FILEPATH='{SITE_DIR}/order_statuses.yaml',
                ORDER_TRANSITIONS_FILEPATH='{SITE_DIR}/order_transitions.yaml',
                ORDERS_LIST_FIELDS=[],
                ORDERS_LIST_STATUSES=[],
                ORDER_MESSAGES_FILEPATH='{SITE_DIR}/order_messages.yaml',
                UNIVERSITIES_FILEPATH='{SITE_DIR}/swedish_universities.yaml',
                COUNTRY_CODES_FILEPATH='{SITE_DIR}/country_codes.yaml',
                SUBJECT_TERMS_FILEPATH='{SITE_DIR}/subjects.yaml',
                DOCUMENTATION_URL='https://github.com/pekrau/OrderPortal/wiki',
                MARKDOWN_URL='http://daringfireball.net/projects/markdown/',
                )
