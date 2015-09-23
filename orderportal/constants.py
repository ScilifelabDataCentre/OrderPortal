" OrderPortal: Various constants."

from __future__ import print_function, absolute_import

import re
import os.path

# Patterns
ID_RX    = re.compile(r'^[a-z][_a-z0-9]*$', re.IGNORECASE)
NAME_RX  = re.compile(r'^[^/]+$')
IUID_RX  = re.compile(r'^[0-9a-f]{32}$')
DATE_RX  = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$') # Safe until 9999 CE...
EMAIL_RX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

# Content types (MIME types)
JSON_MIME      = 'application/json'

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
HIGH_CHAR = 'ZZZZZZZZ'

# Entity documents
DOCTYPE = 'orderportal_doctype'
ACCOUNT = 'account'
GROUP   = 'group'
FIELD   = 'field'
FORM    = 'form'
ORDER   = 'order'
NEWS    = 'news'
EVENT   = 'event'
TEXT    = 'text'
INFO    = 'info'
FILE    = 'file'
LOG     = 'log'
ENTITIES = frozenset([ACCOUNT, GROUP, FIELD, FORM, ORDER, INFO, FILE])

# Field types
STRING  = 'string'
INT     = 'int'
FLOAT   = 'float'
BOOLEAN = 'boolean'
URL     = 'url'
SELECT  = 'select'
TEXT    = 'text'
DATE    = 'date'
### This constant already defined above.
### GROUP   = 'group'
TYPES   = [STRING, INT, FLOAT, BOOLEAN, URL, SELECT, TEXT, DATE, GROUP]
TYPE_LABELS = {INT: 'integer'}
TYPE_HTML = {STRING: 'text', INT: 'number'}

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# User login account
USER_COOKIE = 'orderportal_user'

# Account state
PENDING  = 'pending'
ENABLED  = 'enabled'
DISABLED = 'disabled'
ACCOUNT_STATUSES = [PENDING, ENABLED, DISABLED]

# Account role
USER  = 'user'
STAFF = 'staff'
ADMIN = 'admin'
ACCOUNT_ROLES = [USER, STAFF, ADMIN]

# Form statuses; hard-wired!
TESTING = 'testing'
FORM_STATUSES = [PENDING, TESTING, ENABLED, DISABLED]

# To be filled in from separate YAML file
ORDER_STATES = {}
ORDER_TRANSITIONS = {}

# Password
MIN_PASSWORD_LENGTH = 6

# Display
DEFAULT_PAGE_SIZE = 20
MAX_ACCOUNT_RECENT_ORDERS = 5
MAX_STAFF_RECENT_ORDERS = 20
DEFAULT_MAX_DISPLAY_LOG = 20

# Source code directory
ROOT = os.path.dirname(__file__)
