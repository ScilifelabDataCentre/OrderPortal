"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '2.4.3'

# Default settings, may be changed in a settings YAML file.
settings = dict(
    BASE_URL='http://localhost:8885/',
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
    SITE_DIR='{ROOT}/generic',
    SITE_NAME='OrderPortal',
    DB_SERVER='http://localhost:5984/',
    JQUERY_URL='https://code.jquery.com/jquery-1.12.3.min.js',
    JQUERY_UI_URL='https://code.jquery.com/ui/1.11.4/jquery-ui.min.js',
    JQUERY_UI_THEME_URL='https://code.jquery.com/ui/1.11.4/themes/smoothness/jquery-ui.css',
    BOOTSTRAP_CSS_URL='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/css/bootstrap.min.css',
    BOOTSTRAP_JS_URL='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/js/bootstrap.min.js',
    DATATABLES_CSS_URL='https://cdn.datatables.net/1.10.11/css/dataTables.bootstrap.min.css',
    DATATABLES_JS_URL='https://cdn.datatables.net/1.10.11/js/jquery.dataTables.min.js',
    DATATABLES_BOOTSTRAP_JS_URL='https://cdn.datatables.net/1.10.11/js/dataTables.bootstrap.min.js',
    LOGIN_MAX_AGE_DAYS=14,
    LOGIN_MAX_FAILURES=6,
    ORDERS_DISPLAY_MOST_RECENT=800,
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
