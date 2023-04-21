"Load settings from file and from the database."

import logging
import os
import os.path
import urllib.parse

import dotenv
import yaml

from orderportal import constants, settings


DEFAULT_SETTINGS = dict(
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    BASE_URL="http://localhost:8881/",
    BASE_URL_PATH_PREFIX=None,
    PORT=8881,  # The port used by tornado.
    DATABASE_SERVER="http://localhost:5984/",
    DATABASE_NAME="orderportal",
    DATABASE_ACCOUNT="orderportal_account",
    DATABASE_PASSWORD=None,
    COOKIE_SECRET=None,
    PASSWORD_SALT=None,
    SETTINGS_FILE=None,         # This value is set on startup.
    SETTINGS_ENVVAR=False,      # This value is set on startup.
    SITE_NAME="OrderPortal",
    SITE_FAVICON="orderportal32.png",
    SITE_NAVBAR_ICON="orderportal32.png",
    SITE_HOME_ICON="orderportal144.png",
    SITE_CSS_FILE=None,
    SITE_HOST_URL=None,
    SITE_HOST_ICON=None,
    SITE_HOST_TITLE=None,
    ORDER_IDENTIFIER_FORMAT="OP{0:=05d}", # Order identifier format; site-unique prefix.
    ORDER_IDENTIFIER_FIRST=1,
    MAIL_SERVER=None,  # If not set, then no emails can be sent.
    MAIL_DEFAULT_SENDER=None,  # If not set, MAIL_USERNAME will be used.
    MAIL_PORT=25,
    MAIL_USE_SSL=False,
    MAIL_USE_TLS=False,
    MAIL_EHLO=None,
    MAIL_USERNAME=None,
    MAIL_PASSWORD=None,
    MAIL_REPLY_TO=None,
)


def load_settings_from_file():
    """Load the settings that are not stored in the database from file or
    environment variables.
    1) Initialize with the values in DEFAULT_SETTINGS.
    2) Set environment variables from file '.env', if any, using 'dotenv.load_dotenv'.
       This does not overwrite any already existing environment variables.
    3) Try the filepath in environment variable ORDERPORTAL_SETTINGS_FILEPATH.
    4) If none, try the file '../site/settings.yaml' relative to this directory.
    5) Use any environment variables defined; settings file values are overwritten.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if a settings variable value is invalid.
    """
    if not os.path.exists(constants.SITE_DIR):
        raise OSError(f"""The required site directory '{constants.SITE_DIR}' does not exist.""")
    if not os.path.isdir(constants.SITE_DIR):
        raise OSError(f"""The site directory path '{constants.SITE_DIR}' is not a directory.""")

    settings.clear()
    settings.update(DEFAULT_SETTINGS)

    # Dotenv file '.env' is optional. It is useful for development.
    if dotenv.load_dotenv():
        config["SETTINGS_DOTENV_FILEPATH"] = dotenv.find_dotenv()

    # Find and read the settings file, updating the defaults.
    try:
        filepath = os.environ["ORDERPORTAL_SETTINGS_FILEPATH"]
    except KeyError:
        filepath = os.path.join(constants.SITE_DIR, "settings.yaml")
    try:
        with open(filepath) as infile:
            from_settings_file = yaml.safe_load(infile)
    except OSError:
        obsolete_keys = []
    else:
        settings.update(from_settings_file)
        settings["SETTINGS_FILE"] = filepath
        obsolete_keys = set(from_settings_file.keys()).difference(DEFAULT_SETTINGS)

    # Modify the settings from environment variables; convert to correct type.
    envvar_keys = []
    for key, value in DEFAULT_SETTINGS.items():
        try:
            new = os.environ[key]
        except KeyError:
            pass
        else:  # Do NOT catch any exception! Means bad setup.
            if isinstance(value, int):
                settings[key] = int(new)
            elif isinstance(value, bool):
                settings[key] = utils.to_bool(new)
            else:
                settings[key] = new
            envvar_keys.append(key)
            settings["SETTINGS_ENVVAR"] = True

    # Setup logging.
    logging.basicConfig(format=constants.LOGGING_FORMAT)
    logger = logging.getLogger("orderportal")
    if settings.get("LOGGING_DEBUG"):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.info(f"OrderPortal version {constants.VERSION}")
    logger.info(f"ROOT_DIR: {constants.ROOT_DIR}")
    logger.info(f"SITE_DIR: {constants.SITE_DIR}")
    logger.info(f"settings: {settings['SETTINGS_FILE']}")
    logger.info(f"logger debug: {settings['LOGGING_DEBUG']}")
    logger.info(f"tornado debug: {settings['TORNADO_DEBUG']}")

    # Sanity checks.
    if not settings["PASSWORD_SALT"]:
        raise ValueError("setting PASSWORD_SALT has not been set.")
    if not settings["COOKIE_SECRET"]:
        raise ValueError("setting COOKIE_SECRET has not been set.")
    if len(settings["COOKIE_SECRET"]) < 10:
        raise ValueError("setting COOKIE_SECRET is too short.")

    # Check valid order identifier format; prefix all upper case characters.
    if not settings["ORDER_IDENTIFIER_FORMAT"]:
        raise ValueError("Undefined ORDER_IDENTIFIER_FORMAT")
    if not settings["ORDER_IDENTIFIER_FORMAT"][0].isalpha():
        raise ValueError(
            "ORDER_IDENTIFIER_FORMAT prefix must contain at least one alphabetical character"
        )
    for c in settings["ORDER_IDENTIFIER_FORMAT"]:
        if c.isdigit():
            raise ValueError("ORDER_IDENTIFIER_FORMAT prefix may not contain digits")
        elif not c.isalpha():
            break
        elif c != c.upper():
            raise ValueError(
                "ORDER_IDENTIFIER_FORMAT prefix must be all upper-case characters"
            )
    if not isinstance(settings["ORDER_IDENTIFIER_FIRST"], int):
        raise ValueError("ORDER_IDENTIFIER_FIRST is not an integer")

    # Normalize the BASE_URL and BASE_URL_PATH_PREFIX values.
    # BASE_URL must contain only the scheme and netloc parts, with a trailing '/'.
    # BASE_URL_PATH_PREFIX, if any, must not contain any leading or trailing '/'.
    parts = urllib.parse.urlparse(settings["BASE_URL"])
    settings["BASE_URL"] = f"{parts.scheme}://{parts.netloc}/"
    if parts.path:
        if settings.get("BASE_URL_PATH_PREFIX"):
            raise ValueError("BASE_URL_PATH_PREFIX may not be set if BASE_URL has a path part.")
        settings["BASE_URL_PATH_PREFIX"] = parts.path
    if settings["BASE_URL_PATH_PREFIX"]:
        settings["BASE_URL_PATH_PREFIX"] = settings["BASE_URL_PATH_PREFIX"].strip("/") or None

    # Check for obsolete settings.
    for key in sorted(obsolete_keys):
        logger.warning(f"Obsolete entry '{key}' in settings file.")


def load_settings_from_db(db):
    "Load the configurations that are stored in the database into 'settings'."
    logger = logging.getLogger("orderportal")
    doc = db["order_statuses"]
    settings["ORDER_STATUSES"] = doc["statuses"]
    settings["ORDER_TRANSITIONS"] = doc["transitions"]
    logger.info("Loaded order statuses configuration from database into 'settings'.")

    settings["ORDER_MESSAGES"] = dict([(status, dict(recipients=[], subject="", text=""))
                                       for status in constants.ORDER_STATUSES])
    for status in doc["statuses"]:
        settings["ORDER_MESSAGES"][status["identifier"]] = status["message"]
    logger.info("Loaded order messages configuration from database into 'settings'.")

    doc = db["order"]
    settings["ORDER_CREATE_USER"] = doc.get("create_user", True)
    settings["ORDER_AUTOPOPULATE"] = doc.get("autopopulate", {}) or {}
    settings["ORDER_TAGS"] = doc.get("tags", True)
    settings["ORDER_USER_TAGS"] = doc.get("user_tags", True)
    settings["ORDER_LINKS"] = doc.get("links", True)
    settings["ORDER_REPORTS"] = doc.get("reports", True)
    settings["DISPLAY_MAX_RECENT_ORDERS"] = doc.get("display_max_recent", 10)
    settings["TERMINOLOGY"] = doc.get("terminology", {})
    logger.info("Loaded order configuration from database into 'settings'.")

    doc = db["orders_list"]
    settings["ORDERS_LIST_OWNER_UNIVERSITY"] = doc.get("owner_university", False)
    settings["ORDERS_LIST_OWNER_DEPARTMENT"] = doc.get("owner_department", False)
    settings["ORDERS_LIST_OWNER_GENDER"] = doc.get("owner_gender", False)
    settings["ORDERS_LIST_TAGS"] = doc["tags"]
    settings["ORDERS_LIST_STATUSES"] = doc["statuses"]
    settings["ORDERS_LIST_FIELDS"] = doc["fields"]
    settings["ORDERS_FILTER_FIELDS"] = doc["filters"]
    settings["DISPLAY_ORDERS_MOST_RECENT"] = doc["max_most_recent"]
    settings["DEFAULT_ORDER_COLUMN"] = doc["default_order_column"]
    settings["DEFAULT_ORDER_SORT"] = doc["default_order_sort"]
    logger.info("Loaded orders list configuration from database into 'settings'.")

    doc = db["account"]
    settings["ACCOUNT_REGISTRATION_OPEN"] = doc["registration_open"]
    settings["ACCOUNT_PI_INFO"] = doc["pi_info"]
    settings["ACCOUNT_ORCID_INFO"] = doc["orcid_info"]
    settings["ACCOUNT_ORCID_REQUIRED"] = doc.get("orcid_required", False)
    settings["ACCOUNT_POSTAL_INFO"] = doc["postal_info"]
    settings["ACCOUNT_INVOICE_INFO"] = doc["invoice_info"]
    settings["ACCOUNT_INVOICE_REF_REQUIRED"] = doc["invoice_ref_required"]
    settings["ACCOUNT_FUNDER_INFO_GENDER"] = doc["funder_info_gender"]
    settings["ACCOUNT_FUNDER_INFO_GROUP_SIZE"] = doc["funder_info_group_size"]
    settings["ACCOUNT_FUNDER_INFO_SUBJECT"] = doc["funder_info_subject"]
    settings["ACCOUNT_DEFAULT_COUNTRY_CODE"] = doc["default_country_code"]
    settings["UNIVERSITIES"] = doc["universities"]
    settings["SUBJECT_TERMS"] = doc["subject_terms"]
    settings["LOGIN_MAX_AGE_DAYS"] = doc.get("login_max_age_days", 14)
    settings["LOGIN_MAX_FAILURES"] = doc.get("login_max_failures", 6)
    settings["MIN_PASSWORD_LENGTH"] = doc.get("min_password_length", 8)
    logger.info("Loaded account configuration from database into 'settings'.")

    doc = db["display"]
    settings["DISPLAY_DEFAULT_PAGE_SIZE"] = doc["default_page_size"]
    settings["DISPLAY_MAX_PENDING_ACCOUNTS"] = doc["max_pending_accounts"]
    settings["DISPLAY_TEXT_MARKDOWN_NOTATION_INFO"] = doc["text_markdown_notation_info"]
    settings["DISPLAY_MENU_LIGHT_THEME"] = doc["menu_light_theme"]
    settings["DISPLAY_MENU_ITEM_URL"] = doc["menu_item_url"]
    settings["DISPLAY_MENU_ITEM_TEXT"] = doc["menu_item_text"]
    settings["DISPLAY_MENU_INFORMATION"] = doc["menu_information"]
    settings["DISPLAY_MENU_DOCUMENTS"] = doc["menu_documents"]
    settings["DISPLAY_MENU_CONTACT"] = doc["menu_contact"]
    settings["DISPLAY_MENU_ABOUT_US"] = doc["menu_about_us"]
    logger.info("Loaded display configuration from database into 'settings'.")

    # Lookup for the enabled statuses: key=identifier, value=item dict.
    settings["ORDER_STATUSES_LOOKUP"] = dict(
        [(s["identifier"], s) for s in settings["ORDER_STATUSES"] if s.get("enabled")]
    )

    # Lookup for subject terms: key=code, value=item dict.
    settings["SUBJECT_TERMS_LOOKUP"] = dict(
        [(s["code"], s["term"]) for s in settings["SUBJECT_TERMS"]]
    )

    # Site configuration variables and files.
    doc = db["site_configuration"]
    settings["SITE_NAME"] = doc.get("name") or "OrderPortal"
    settings["SITE_HOST_NAME"] = doc.get("host_name")
    settings["SITE_HOST_URL"] = doc.get("host_url")
    for name in ("icon", "favicon", "image", "css", "host_icon"):
        key = f"SITE_{name.upper()}"
        if doc.get("_attachments", {}).get(name):
            settings[key] = dict(
                content_type=doc["_attachments"][name]["content_type"],
                content=db.get_attachment(doc, name).read()
            )
        else:
            settings[key] = None


def load_texts_from_db(db):
    "Load the texts from the database into settings."
    for type in (
        constants.DISPLAY,
        constants.ACCOUNT,
        constants.ORDER,
        constants.REPORT,
    ):
        docs = [row.doc for row in db.view("text", "type", type, include_docs=True)]
        settings[type] = dict()
        for doc in docs:
            settings[type][doc["name"]] = doc
