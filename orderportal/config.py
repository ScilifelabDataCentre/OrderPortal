"Load settings from file and from the database."

import logging
import os
import os.path
import urllib.parse

import yaml

from orderportal import constants, settings, DEFAULT_SETTINGS


def load_settings_from_file():
    """Load the settings that are not in the database from file.
    1) Initialize with the values in DEFAULT_SETTINGS.
    2) Try the filepath in environment variable ORDERPORTAL_SETTINGS.
    3) If none, try the file '../site/settings.yaml' relative to this directory.
    Raise OSError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if a settings variable value is invalid.
    """
    if not os.path.exists(constants.SITE_DIR):
        raise OSError(f"""The required site directory '{constants.SITE_DIR}' does not exist.""")
    if not os.path.isdir(constants.SITE_DIR):
        raise OSError(f"""The site directory path '{constants.SITE_DIR}' is not a directory.""")

    # Find and read the settings file, updating the defaults.
    try:
        filepath = os.environ["ORDERPORTAL_SETTINGS"]
    except KeyError:
        filepath = os.path.join(constants.SITE_DIR, "settings.yaml")
    with open(filepath) as infile:
        from_settings_file = yaml.safe_load(infile)
    settings.update(from_settings_file)
    settings["SETTINGS_FILE"] = filepath

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

    # Check some settings.
    for key in [
        "BASE_URL",
        "DATABASE_SERVER",
        "DATABASE_NAME",
        "DATABASE_ACCOUNT",
        "DATABASE_PASSWORD",
        "COOKIE_SECRET",
        "PASSWORD_SALT",
    ]:
        if not settings[key]:
            raise ValueError(f"settings['{key}'] has invalid value.")
    if len(settings["COOKIE_SECRET"]) < 10:
        raise ValueError("settings['COOKIE_SECRET'] is too short.")

    # Check valid order identifier format; prefix all upper case characters
    if not settings["ORDER_IDENTIFIER_FORMAT"]:
        raise ValueError("Undefined ORDER_IDENTIFIER_FORMAT")
    if not isinstance(settings["ORDER_IDENTIFIER_FIRST"], int):
        raise ValueError("ORDER_IDENTIFIER_FIRST is not an integer")
    if not settings["ORDER_IDENTIFIER_FORMAT"][0].isalpha():
        raise ValueError(
            "ORDER_IDENTIFIER_FORMAT prefix contain at least one alphabetical character"
        )
    for c in settings["ORDER_IDENTIFIER_FORMAT"]:
        if not c.isalpha():
            break
        if not c.isupper():
            raise ValueError(
                "ORDER_IDENTIFIER_FORMAT prefix must be all upper-case characters"
            )

    # Check for obsolete settings.
    for key in sorted(from_settings_file):
        if key not in DEFAULT_SETTINGS:
            logger.warning(f"Obsolete entry '{key}' in settings file.")

    # Read order messages YAML file.
    filepath = settings.get("ORDER_MESSAGES_FILE")
    if filepath:
        filepath = os.path.join(constants.SITE_DIR, filepath)
        logger.info(f"Order messages file: {filepath}")
        with open(filepath) as infile:
            settings["ORDER_MESSAGES"] = yaml.safe_load(infile) or {}
    else:
        settings["ORDER_MESSAGES"] = {}

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


def load_settings_from_db(db):
    "Load the configuration that are stored in the database into 'settings'."
    logger = logging.getLogger("orderportal")
    doc = db["order_statuses"]
    settings["ORDER_STATUSES"] = doc["statuses"]
    settings["ORDER_TRANSITIONS"] = doc["transitions"]
    logger.info("Loaded order statuses configuration from database into 'settings'.")

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
