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
    site_dir = settings["SITE_DIR"]
    if not os.path.exists(site_dir):
        raise OSError(f"The required site directory '{site_dir}' does not exist.")
    if not os.path.isdir(site_dir):
        raise OSError(f"The site directory path '{site_dir}' is not a directory.")

    # Find and read the settings file, updating the defaults.
    try:
        filepath = os.environ["ORDERPORTAL_SETTINGS"]
    except KeyError:
        filepath = os.path.join(site_dir, "settings.yaml")
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
    logger.info(f"ROOT: {constants.ROOT}")
    logger.info(f"SITE_DIR: {settings['SITE_DIR']}")
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
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logger.info(f"Order messages file: {filepath}")
        with open(filepath) as infile:
            settings["ORDER_MESSAGES"] = yaml.safe_load(infile) or {}
    else:
        settings["ORDER_MESSAGES"] = {}

    # Read universities YAML file.
    filepath = settings.get("UNIVERSITIES_FILE")
    if filepath:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logger.info(f"Universities lookup file: {filepath}")
        with open(filepath) as infile:
            unis = yaml.safe_load(infile) or {}
        unis = list(unis.items())
        unis.sort(key=lambda i: (i[1].get("rank"), i[0]))
        settings["UNIVERSITIES"] = dict(unis)
    else:
        settings["UNIVERSITIES"] = {}

    # Read subject terms YAML file.
    filepath = settings.get("SUBJECT_TERMS_FILE")
    if filepath:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logger.info(f"Subject terms file: {filepath}")
        with open(filepath) as infile:
            settings["SUBJECT_TERMS"] = yaml.safe_load(infile) or []
    else:
        settings["SUBJECT_TERMS"] = []
    settings["SUBJECT_TERMS_LOOKUP"] = dict(
        [(s["code"], s["term"]) for s in settings["SUBJECT_TERMS"]]
    )

    # Settings computable from others.
    parts = urllib.parse.urlparse(settings["BASE_URL"])
    if not settings.get("BASE_URL_PATH_PREFIX") and parts.path:
        settings["BASE_URL_PATH_PREFIX"] = parts.path.rstrip("/") or None
    # BASE_URL should not contain any path part.
    settings["BASE_URL"] = "%s://%s/" % (parts.scheme, parts.netloc)


def load_settings_from_db(db):
    """Load the settings that are stored in the database:
    - order statuses and transitions
    - orders list settings
    and setup derived variable values.
    """
    logger = logging.getLogger("orderportal")
    doc = db["order_statuses"]
    settings["ORDER_STATUSES"] = doc["statuses"]
    settings["ORDER_TRANSITIONS"] = doc["transitions"]
    logger.info("Loaded order statuses from database into 'settings'.")

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
    logger.info("Loaded orders list settings from database into 'settings'.")

    doc = db["account"]
    settings["ACCOUNT_REGISTRATION_OPEN"] = doc["registration_open"]
    settings["ACCOUNT_PI_INFO"] = doc["pi_info"]
    settings["ACCOUNT_ORCID_INFO"] = doc["orcid_info"]
    settings["ACCOUNT_POSTAL_INFO"] = doc["postal_info"]
    settings["ACCOUNT_INVOICE_INFO"] = doc["invoice_info"]
    settings["ACCOUNT_INVOICE_REF_REQUIRED"] = doc["invoice_ref_required"]
    settings["ACCOUNT_FUNDER_INFO_GENDER"] = doc["funder_info_gender"]
    settings["ACCOUNT_FUNDER_INFO_GROUP_SIZE"] = doc["funder_info_group_size"]
    settings["ACCOUNT_FUNDER_INFO_SUBJECT"] = doc["funder_info_subject"]
    settings["ACCOUNT_DEFAULT_COUNTRY_CODE"] = doc["default_country_code"]
    logger.info("Loaded account settings from database into 'settings'.")

    # Lookup for the enabled statuses.
    settings["ORDER_STATUSES_LOOKUP"] = dict(
        [(s["identifier"], s) for s in settings["ORDER_STATUSES"] if s.get("enabled")]
    )

    # Find the initial status.
    for status in settings["ORDER_STATUSES"]:
        if status.get("initial"):
            settings["ORDER_STATUS_INITIAL"] = status
