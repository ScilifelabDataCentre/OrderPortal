"""OrderPortal: A portal for orders to a facility from its users.
An order can be a project application, a request, a report, etc.
"""

import os.path
import re
import sys

__version__ = "7.0.12"


class Constants:
    def __setattr__(self, key, value):
        raise ValueError("setting constant is not allowed")

    VERSION = __version__
    SOURCE_URL = "https://github.com/pekrau/OrderPortal"
    ROOT = os.path.dirname(os.path.abspath(__file__))

    PYTHON_VERSION = ".".join([str(i) for i in sys.version_info[0:3]])
    PYTHON_URL = "https://www.python.org/"

    TORNADO_URL = "https://pypi.org/project/tornado/"
    COUCHDB_URL = "https://couchdb.apache.org/"
    COUCHDB2_URL = "https://pypi.org/project/couchdb2"
    REQUESTS_URL = "https://docs.python-requests.org/"
    XLSXWRITER_URL = "https://pypi.org/project/XlsxWriter/"
    MARKDOWN_URL = "https://pypi.org/project/Markdown/"
    PYYAML_URL = "https://pypi.org/project/PyYAML/"

    BOOTSTRAP_VERSION = "3.4.1"
    BOOTSTRAP_URL = "https://getbootstrap.com/docs/3.4/"

    JQUERY_VERSION = "1.12.4"
    JQUERY_URL = "https://jquery.com/"

    JQUERY_UI_VERSION = "1.11.4"

    JQUERY_LOCALTIME_VERSION = "0.9.1"
    JQUERY_LOCALTIME_URL = "https://plugins.jquery.com/jquery.localtime/"

    DATATABLES_VERSION = "1.10.11"
    DATATABLES_URL = "https://datatables.net/"

    # Patterns
    ID_RX = re.compile(r"^[a-z][_a-z0-9]*$", re.IGNORECASE)
    NAME_RX = re.compile(r"^[^/]+$")
    IUID_RX = re.compile(r"^[0-9a-f]{32}$")
    DATE_RX = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")  # Works until 9999 CE...
    EMAIL_RX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

    # CouchDB
    # For view ranges: CouchDB uses the Unicode Collation Algorithm,
    # which is not the same as the ASCII collation sequence.
    # The endkey is inclusive, by default.
    CEILING = "ZZZZZZZZ"

    # Entity document types
    DOCTYPE = "orderportal_doctype"
    ACCOUNT = "account"
    GROUP = "group"
    FORM = "form"
    ORDER = "order"
    NEWS = "news"
    EVENT = "event"
    TEXT = "text"
    INFO = "info"
    FILE = "file"
    MESSAGE = "message"
    LOG = "log"
    META = "meta"
    ENTITIES = frozenset([ACCOUNT, GROUP, FORM, ORDER, INFO, FILE, MESSAGE])

    # System attachments to order
    SYSTEM = "system"
    SYSTEM_REPORT = "system_report"

    # Field types
    STRING = "string"
    EMAIL = "email"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    SELECT = "select"
    MULTISELECT = "multiselect"
    ### TEXT = "text" Already defined above.
    DATE = "date"
    TABLE = "table"
    ### GROUP   = 'group'
    ### FILE    = 'file' Already defined above.
    TYPES = [
        STRING,
        EMAIL,
        INT,
        FLOAT,
        BOOLEAN,
        URL,
        SELECT,
        MULTISELECT,
        TEXT,
        DATE,
        TABLE,
        FILE,
        GROUP,
    ]
    TYPE_HTML = {
        STRING: "text",
        INT: "number",
        DATE: "date",
        EMAIL: "email",
        URL: "url",
    }
    # Step for use with input type 'float'
    FLOAT_STEP = "0.0000001"

    # Banned meta document id's; have changed format or been removed.
    # Re-using these id's would likely create backwards incompatibility issues.
    BANNED_META_IDS = frozenset(["account_messages", "order_messages", "global_modes"])

    # Text types
    DISPLAY = "display"
    ### ACCOUNT = "account" Already defined above.
    ### ORDER = "order" Already defined above.

    # Boolean string values
    TRUE = frozenset(["true", "yes", "t", "y", "1"])
    FALSE = frozenset(["false", "no", "f", "n", "0"])

    # User login account
    USER_COOKIE = "orderportal_user"
    API_KEY_HEADER = "X-OrderPortal-API-key"

    # Account statuses; hard-wired!
    PENDING = "pending"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ACCOUNT_STATUSES = [PENDING, ENABLED, DISABLED]
    RESET = "reset"

    # Account role
    USER = "user"
    STAFF = "staff"
    ADMIN = "admin"
    ACCOUNT_ROLES = [USER, STAFF, ADMIN]

    # Form status; hard-wired!
    TESTING = "testing"
    FORM_STATUSES = [PENDING, TESTING, ENABLED, DISABLED]

    # Hard-wired order statuses; must always be present.
    PREPARATION = "preparation"
    SUBMITTED = "submitted"

    # Content types (MIME types)
    HTML_MIME = "text/html"
    JSON_MIME = "application/json"
    CSV_MIME = "text/csv"
    ZIP_MIME = "application/zip"
    TEXT_MIME = "text/plain"
    BIN_MIME = "application/octet-stream"
    PDF_MIME = "application/pdf"
    JPEG_MIME = "image/jpeg"
    PNG_MIME = "image/png"
    XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    XLSM_MIME = "application/vnd.ms-excel.sheet.macroEnabled.12"

    # Hard-wired mapping content type -> extension (overriding mimetypes module)
    MIME_EXTENSIONS = {TEXT_MIME: ".txt",
                       JPEG_MIME: ".jpg",
                       XLSM_MIME: ".xlsm",
                       XLSX_MIME: ".xlsx"}

    # Content-type to icon mapping
    CONTENT_TYPE_ICONS = {
        JSON_MIME: "json.png",
        CSV_MIME: "csv.png",
        TEXT_MIME: "text.png",
        HTML_MIME: "html.png",
        PDF_MIME: "pdf.png",
        PNG_MIME: "image.png",
        JPEG_MIME: "image.png",
        "application/vnd.ms-excel": "excel.png",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel.png",
        "application/vnd.ms-excel": "excel.png",
        XLSX_MIME: "excel.png",
        XLSM_MIME: "excel.png",
        "application/msword": "word.png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word.png",
        "application/vnd.ms-powerpoint": "ppt.png",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "ppt.png",
    }
    DEFAULT_CONTENT_TYPE_ICON = "binary.png"
    VIEWABLE_CONTENT_TYPES = set([TEXT_MIME, JSON_MIME, CSV_MIME, PDF_MIME])

constants = Constants()


# Default settings. Some of these need to be set in the 'site/settings.yaml' file.
settings = dict(
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    LOGGING_FORMAT="%(levelname)s [%(asctime)s] %(message)s",
    LOGGING_FILEPATH=None,
    LOGGING_FILEMODE=None,
    BASE_URL="http://localhost:8881/",
    BASE_URL_PATH_PREFIX=None,
    PORT=8881,  # The port used by tornado.
    PIDFILE=None,
    DATABASE_SERVER="http://localhost:5984/",
    DATABASE_NAME="orderportal",
    DATABASE_ACCOUNT="orderportal_account",
    DATABASE_PASSWORD="CHANGE THIS!",
    COOKIE_SECRET="CHANGE THIS!",
    PASSWORD_SALT="CHANGE THIS!",
    MIN_PASSWORD_LENGTH=8,
    MARKDOWN_URL="https://www.markdownguide.org/basic-syntax/",
    SITE_DIR=os.path.normpath(os.path.join(constants.ROOT, "../site")),
    SITE_STATIC_DIR=os.path.normpath(os.path.join(constants.ROOT, "../site/static")),
    SITE_NAME="OrderPortal",
    SITE_SUPPORT_EMAIL=None,
    SITE_FAVICON="orderportal32.png",
    SITE_NAVBAR_ICON="orderportal32.png",
    SITE_HOME_ICON="orderportal144.png",
    SITE_CSS_FILE=None,
    SITE_HOST_URL=None,
    SITE_HOST_ICON=None,
    SITE_HOST_TITLE=None,
    DISPLAY_MENU_LIGHT=False,
    DISPLAY_MENU_ITEM_URL=None,
    DISPLAY_MENU_ITEM_TEXT=None,
    ACCOUNT_MESSAGES_FILE="account_messages.yaml",
    ORDER_MESSAGES_FILE="order_messages.yaml",
    COUNTRY_CODES_FILE="country_codes.yaml",
    UNIVERSITIES_FILE="swedish_universities.yaml",
    SUBJECT_TERMS_FILE="subject_terms.yaml",
    TERMINOLOGY=dict(),         # Terms translation lookup.
    LOGIN_MAX_AGE_DAYS=14,      # Max age of login session in a browser.
    LOGIN_MAX_FAILURES=6,       # After this number of fails, the account is disabled.
    ORDER_CREATE_USER=True,
    ORDER_IDENTIFIER_FORMAT="OP{0:=05d}",
    ORDER_IDENTIFIER_FIRST=1,
    ORDER_TAGS=True,
    ORDER_USER_TAGS=True,
    ORDER_LINKS=True,
    ORDER_REPORT=True,
    ORDERS_SEARCH_DELIMS_LINT=[":", ",", ";", "'"],
    ORDERS_SEARCH_LINT=["an", "to", "in", "on", "of", "and", "the", "is", "was", "not"],
    ACCOUNT_REGISTRATION_OPEN=True,
    ACCOUNT_PI_INFO=True,
    ACCOUNT_ORCID_INFO=True,
    ACCOUNT_POSTAL_INFO=True,
    ACCOUNT_INVOICE_INFO=True,
    ACCOUNT_INVOICE_REF_REQUIRED=False,
    ACCOUNT_FUNDER_INFO=True,
    ACCOUNT_FUNDER_INFO_GENDER=True,
    ACCOUNT_FUNDER_INFO_GROUP_SIZE=True,
    ACCOUNT_FUNDER_INFO_SUBJECT=True,
    ACCOUNT_DEFAULT_COUNTRY_CODE="SE",
    EMAIL=dict(
        HOST=None,  # Domain name. Must be defined for email to work.
        PORT=0,
        SSL=False,
        TLS=False,
        USER=None,
        PASSWORD=None,
    ),
    MESSAGE_SENDER_EMAIL='"OrderPortal Support" <support@my-domain.com>', # Required.
    MESSAGE_REPLY_TO_EMAIL=None,  # Same format as above; optional.
    DISPLAY_DEFAULT_PAGE_SIZE=25, # Number of paged items in a table.
    DISPLAY_MAX_RECENT_ORDERS=10, # Max number in home page for admin and staff.
    DISPLAY_MAX_PENDING_ACCOUNTS=10, # Max number in home page for admin and staff.
    DISPLAY_DEFAULT_MAX_LOG=20,     # Max number of log items displayed.
    DISPLAY_NEWS=True,
    DISPLAY_MAX_NEWS=4,
    DISPLAY_EVENTS=True,
    DISPLAY_MENU_INFORMATION=True,
    DISPLAY_MENU_DOCUMENTS=True,
    DISPLAY_MENU_CONTACT=True,
    DISPLAY_MENU_ABOUT_US=True,
    DISPLAY_TEXT_MARKDOWN_NOTATION_INFO=True,
)

# In-memory copy of various configuration values such as order statuses and transitions.
# Read from the database on server startup. Modifiable via the web interface.
parameters = {}
