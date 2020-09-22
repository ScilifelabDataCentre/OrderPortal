"Various constants."



import re

# Patterns
ID_RX    = re.compile(r'^[a-z][_a-z0-9]*$', re.IGNORECASE)
NAME_RX  = re.compile(r'^[^/]+$')
IUID_RX  = re.compile(r'^[0-9a-f]{32}$')
DATE_RX  = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$') # Safe until 9999 CE...
EMAIL_RX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
CEILING = 'ZZZZZZZZ'

# Entity documents
DOCTYPE = 'orderportal_doctype'
ACCOUNT = 'account'
GROUP   = 'group'
FORM    = 'form'
ORDER   = 'order'
NEWS    = 'news'
EVENT   = 'event'
TEXT    = 'text'
INFO    = 'info'
FILE    = 'file'
MESSAGE = 'message'
LOG     = 'log'
META    = 'meta'
ENTITIES = frozenset([ACCOUNT, GROUP, FORM, ORDER, INFO, FILE, MESSAGE])

# System attachments to order
SYSTEM = 'system'
SYSTEM_REPORT = 'system_report'

# Field types
STRING  = 'string'
EMAIL   = 'email'
INT     = 'int'
FLOAT   = 'float'
BOOLEAN = 'boolean'
URL     = 'url'
SELECT  = 'select'
MULTISELECT  = 'multiselect'
TEXT    = 'text'
DATE    = 'date'
TABLE   = 'table'
### This constant already defined above.
### GROUP   = 'group'
### FILE    = 'file'
TYPES = [STRING, EMAIL, INT, FLOAT, BOOLEAN, URL, SELECT, MULTISELECT,
         TEXT, DATE, TABLE, FILE, GROUP]
TYPE_HTML = {STRING: 'text', INT: 'number', DATE: 'date', 
             EMAIL: 'email', URL: 'url'}
# Step for use with input type 'float'
FLOAT_STEP = '0.0000001'

# Texts for use in web site
TEXTS = dict(header='Header on portal home page.',
             register='Registration page.',
             registered='Page after registration.',
             reset='Password reset page.',
             password='Password setting page.',
             general='General information on portal home page.',
             contact='Contact page.',
             about='About page.',
             alert='Alert text at the top of every page.',
             privacy_policy='Privacy policy statement; GDPR, etc.')

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# Default global modes for database initialization
DEFAULT_GLOBAL_MODES = dict(allow_registration=True,
                            allow_login=True,
                            allow_order_creation=True,
                            allow_order_editing=True,
                            allow_order_submission=True)

# User login account
USER_COOKIE = 'orderportal_user'
API_KEY_HEADER = 'X-OrderPortal-API-key'

# Account status; hard-wired!
PENDING  = 'pending'
ENABLED  = 'enabled'
DISABLED = 'disabled'
ACCOUNT_STATUSES = [PENDING, ENABLED, DISABLED]
RESET    = 'reset'

# Account role
USER  = 'user'
STAFF = 'staff'
ADMIN = 'admin'
ACCOUNT_ROLES = [USER, STAFF, ADMIN]

# Hard-wired order status
SUBMIT    = 'submit'
SUBMITTED = 'submitted'

# Form status; hard-wired!
TESTING = 'testing'
FORM_STATUSES = [PENDING, TESTING, ENABLED, DISABLED]

# Content types (MIME types)
HTML_MIME = 'text/html'
JSON_MIME = 'application/json'
CSV_MIME  = 'text/csv'
ZIP_MIME  = 'application/zip'
TEXT_MIME = 'text/plain'
BIN_MIME  = 'application/octet-stream'
PDF_MIME  = 'application/pdf'
JPEG_MIME = 'image/jpeg'
PNG_MIME  = 'image/png'
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
XLSM_MIME = 'application/vnd.ms-excel.sheet.macroEnabled.12'

# Hard-wired mapping content type -> extension (overriding mimetypes module)
MIME_EXTENSIONS = {TEXT_MIME: '.txt',
                   JPEG_MIME: '.jpg',
                   XLSM_MIME: '.xlsm'}

# Content-type to icon mapping
CONTENT_TYPE_ICONS = {
    JSON_MIME: 'json.png',
    CSV_MIME: 'csv.png',
    TEXT_MIME: 'text.png',
    HTML_MIME: 'html.png',
    PDF_MIME: 'pdf.png',
    PNG_MIME: 'image.png',
    JPEG_MIME: 'image.png',
    'application/vnd.ms-excel': 'excel.png',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel.png',
    'application/vnd.ms-excel': 'excel.png',
    XLSX_MIME: 'excel.png',
    XLSM_MIME: 'excel.png',
    'application/msword': 'word.png',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'word.png',
    'application/vnd.ms-powerpoint': 'ppt.png',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'ppt.png',
    }
DEFAULT_CONTENT_TYPE_ICON = 'binary.png'
VIEWABLE_CONTENT_TYPES = set([TEXT_MIME,
                              JSON_MIME,
                              CSV_MIME,
                              PDF_MIME])
