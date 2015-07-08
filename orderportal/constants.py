" OrderPortal: Various constants."

from __future__ import unicode_literals, print_function, absolute_import

import re
import os.path

# Patterns
ID_RX        = re.compile(r'^[a-z][_a-z0-9]*$', re.IGNORECASE)
NAME_RX      = re.compile(r'^[^/]+$')
IUID_RX      = re.compile(r'^[0-9a-f]{32}$')
EMAIL_RX     = re.compile(r'^[^@]+@[^@]+\.[^@]+$')
PASSWORD_LEN = 6

# Content types (MIME types)
JSON_MIME      = 'application/json'

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
HIGH_CHAR = 'ZZZZZZZZ'

# Entity documents
DOCTYPE     = 'orderportal_doctype'
USER        = 'user'
FIELD       = 'field'
FORM        = 'form'
ORDER       = 'order'
PUBLICATION = 'publication'
NEW         = 'new'         # A single news item.
EVENT       = 'event'
USER        = 'user'
TEXT        = 'text'
INFO        = 'info'
LOG         = 'log'
ENTITIES    = frozenset([USER, FIELD, FORM, ORDER, INFO, PUBLICATION, USER])

# Field types
STRING  = 'string'
INT     = 'int'
FLOAT   = 'float'
BOOLEAN = 'boolean'
URL     = 'url'
SELECT  = 'select'
GROUP   = 'group'
TYPES   = [STRING, INT, FLOAT, BOOLEAN, URL, SELECT, GROUP]
TYPE_LABELS = {INT: 'integer'}

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# User
USER_COOKIE    = 'orderportal_user'
API_KEY_HEADER = 'X-Orderportal-Api-Key'
TOKEN_HEADER   = 'X-Orderportal-Token'
# User state
PENDING       = 'pending'
ENABLED       = 'enabled'
DISABLED      = 'disabled'
USER_STATUSES = [PENDING, ENABLED, DISABLED]
# User role
ADMIN      = 'admin'
STAFF      = 'staff'
USER_ROLES = [USER, STAFF, ADMIN]
# Form state
FORM_STATUSES = [PENDING, ENABLED, DISABLED]

# To be filled in from separate YAML file
ORDER_STATES = {}
ORDER_TRANSITIONS = {}

# Password
MIN_PASSWORD_LENGTH = 6

# Display
DEFAULT_MAX_DISPLAY_LOG = 20

# Source code directory
ROOT = os.path.dirname(__file__)
