"Admin pages."

import copy
import logging
import os.path
import re

import couchdb2
import tornado.web
import yaml

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class MetaSaver(saver.Saver):
    doctype = constants.META

    def set_id(self, id):
        if id in constants.BANNED_META_IDS:
            raise ValueError(f"trying to use a banned meta document name '{id}'")
        self.doc["_id"] = id

    def log(self):
        "Don't bother recording log for meta documents."
        pass


DEFAULT_ORDER_STATUSES = [
    dict(
        identifier=constants.PREPARATION, # Hard-wired! Must be present.
        enabled=True,                     # Must be enabled!
        description="The order has been created and is being edited by the user.",
        edit=["user", "staff", "admin"],
        attach=["user", "staff", "admin"],
        action="Prepare",
    ),
    dict(
        identifier=constants.SUBMITTED, # Hard-wired! Must be present.
        enabled=True,                   # Must be enabled!
        description="The order has been submitted by the user for consideration.",
        edit=["staff", "admin"],
        attach=["staff", "admin"],
        action="Submit",
    ),
    dict(
        identifier="review",
        description="The order is under review.",
        edit=["staff", "admin"],
        attach=["staff", "admin"],
        action="Review",
    ),
    dict(
        identifier="queued",
        description="The order has been queued.",
        edit=["admin"],
        attach=["admin"],
        action="Queue",
    ),
    dict(
        identifier="waiting",
        description="The order is waiting.",
        edit=["admin"],
        attach=["admin"],
        action="Wait",
    ),
    dict(
        identifier="accepted",
        description="The order has been checked and accepted.",
        edit=["admin"],
        attach=["admin"],
        action="Accept",
    ),
    dict(
        identifier="rejected",
        description="The order has been rejected.",
        edit=["admin"],
        attach=["admin"],
        action="Reject",
    ),
    dict(
        identifier="processing",
        description="The order is being processed in the lab.",
        edit=["admin"],
        attach=["admin"],
        action="Process",
    ),
    dict(
        identifier="active",
        description="The order is active.",
        edit=["admin"],
        attach=["admin"],
        action="Active",
    ),
    dict(
        identifier="analysis",
        description="The order results are being analysed.",
        edit=["admin"],
        attach=["admin"],
        action="Analyse",
    ),
    dict(
        identifier="onhold",
        description="The order is on hold.",
        edit=["admin"],
        attach=["admin"],
        action="On hold",
    ),
    dict(
        identifier="halted",
        description="The work on the order has been halted.",
        edit=["admin"],
        attach=["admin"],
        action="Halt",
    ),
    dict(
        identifier="aborted",
        description="The work on the order has been permanently stopped.",
        edit=["admin"],
        attach=["admin"],
        action="Abort",
    ),
    dict(
        identifier="terminated",
        description="The order has been terminated.",
        edit=["admin"],
        attach=["admin"],
        action="Terminate",
    ),
    dict(
        identifier="cancelled",
        description="The order has cancelled.",
        edit=["admin"],
        attach=["admin"],
        action="Cancel",
    ),
    dict(
        identifier="finished",
        description="The work on the order has finished.",
        edit=["admin"],
        attach=["admin"],
        action="Finish",
    ),
    dict(
        identifier="completed",
        description="The order has been completed.",
        edit=["admin"],
        attach=["admin"],
        action="Complete",
    ),
    dict(
        identifier="closed",
        description="All work and other actions for the order have been performed.",
        edit=["admin"],
        attach=["admin"],
        action="Closed",
    ),
    dict(
        identifier="delivered",
        description="The order results have been delivered.",
        edit=["admin"],
        attach=["admin"],
        action="Deliver",
    ),
    dict(
        identifier="invoiced",
        description="The order has been invoiced.",
        edit=["admin"],
        attach=["admin"],
        action="Invoice",
    ),
    dict(
        identifier="archived",
        description="The order has been archived.",
        edit=["admin"],
        attach=["admin"],
        action="Archive",
    ),
]


# Minimal, since only 'preparation' and 'submitted' are guaranteed to be enabled.

DEFAULT_ORDER_TRANSITIONS = [
    dict(
        source=constants.PREPARATION,
        targets=[constants.SUBMITTED],
        permission=["user", "admin", "staff"],
        require="valid",
    ),
]


INIT_TEXTS = dict(
    header="""This is a portal for placing orders. You need to have an account and
be logged in to create, edit, submit and view orders.
""",
    register="""In order to place orders, you must have registered an account in this system.
Register here. Your email address is the account name in this portal.

The administrator of the portal will review your account details.
If everything seems fine the account will be enabled.

You will receive an email with a link to a page for setting the password
when the account is enabled.

The personal data you provide in this registration form is to enable
SciLifeLab to: register and contact you about submitted information;
carry out administrative tasks and evaluate your submitted
information; and allow the compilation and analysis of submitted
information for internal purposes.

The information you provide will be processed in accordance with the
Swedish law implementing the EU GDPR directive for the protection of
individuals with regard to the processing of personal data.

By submitting you acknowledge that you have read and understood the
foregoing and consent to the uses of your information as set out
above.
""",
    registered="""An activation email will be sent to you from the administrator
when your account has been enabled. This may take up to two working days.
""",
    reset="""Use this page to reset your password. 

An email with a link to a page for setting a new password will be sent
to you. **This may take a couple of minutes! Check your spam filter.**

The email contains a one-time code for setting a new password, and a link
to the relevant page. If you loose this code, simply do reset again.
""",
    password="""Set the password for your account. You need the one-time code which
was contained in the URL sent to you by email. **Note that it takes a couple
of minutes for the email to reach you.**

If the code does not work, it may have been overwritten or already been used.
Go to [the reset page](/reset) to obtain a new code.
""",
    general="""[Add general information about the facility.]""",
    contact="""[Add information on how to contact the facility.]""",
    about="""[Add information about this site.]""",
    alert="""**NOTE**: This site has not yet been configured.""",
    privacy_policy="""### Privacy policy (GDPR)

The personal data you provide in this registration form is to enable
SciLifeLab to: register and contact you about submitted information;
carry out administrative tasks and evaluate your submitted
information; and allow the compilation and analysis of submitted
information for internal purposes.

The information you provide will be processed in accordance with the
Swedish law implementing the EU GDPR directive for the protection of
individuals with regard to the processing of personal data.

By registering your account, you have acknowledged that you have
read and understood the foregoing and consent to the uses of your
information as set out above.

All your personal data is reachable via links from this page and the
pages for all your orders (link below). The logs for your account
and orders contains the records of all changes to those items.
""",
)


def load_order_statuses(db):
    """Load the order statuses and transitions from the database.
    If not there, get from legacy site YAML files.
    If none, then use default values.
    Save to database, if from default and/or old site setup files.
    Once saved to the database, the legacy site YAML files will no longer
    be used and can be deleted.
    """
    try:
        # From version 6.0.0, the order statuses are in the database.
        doc = db["order_statuses"]
        settings["ORDER_STATUSES"] = doc["statuses"]
        settings["ORDER_TRANSITIONS"] = doc["transitions"]
        logging.info("loaded order statuses from database")

    except couchdb2.NotFoundError:
        # Create the order statuses document in the database.

        # Start with default order statuses setup.
        settings["ORDER_STATUSES"] = copy.deepcopy(DEFAULT_ORDER_STATUSES)
        lookup = dict([(s["identifier"], s) for s in settings["ORDER_STATUSES"]])

        # Load the legacy site order_statuses.yaml file, if any.
        try:
            filepath = os.path.join(
                settings["SITE_DIR"], settings["ORDER_STATUSES_FILE"]
            )
            with open(filepath) as infile:
                legacy_statuses = yaml.safe_load(infile)
            logging.info(f"read legacy order statuses: {filepath}")
        except (KeyError, FileNotFoundError) as error:
            logging.warning(f"defaults used for order statuses; {error}")
        else:
            # Transfer order status data from the legacy setup and flag as enabled.
            lookup = dict([(s["identifier"], s) for s in settings["ORDER_STATUSES"]])
            for status in legacy_statuses:
                try:
                    lookup[status["identifier"]].update(status)
                    lookup[status["identifier"]]["enabled"] = True
                except KeyError:
                    logging.error(
                        f"""unknown legacy order status: '{status["identifier"]}'; skipped"""
                    )

        # Start with the default order transitions setup.
        settings["ORDER_TRANSITIONS"] = copy.deepcopy(DEFAULT_ORDER_TRANSITIONS)

        # Load the legacy site order_transitions.yaml file, if any.
        try:
            filepath = os.path.join(
                settings["SITE_DIR"], settings["ORDER_TRANSITIONS_FILE"]
            )
            with open(filepath) as infile:
                legacy_transitions = yaml.safe_load(infile)
            logging.info(f"loaded legacy order transitions: {filepath}")
        except (KeyError, FileNotFoundError) as error:
            logging.warning(f"defaults used for order transitions; {error}")
        else:
            # Transfer order transitions data from legacy setup.
            for legacy_trans in legacy_transitions:
                # Silently eliminate unknown target statues.
                legacy_trans["targets"] = [
                    t for t in legacy_trans["targets"] if t in lookup
                ]
                for trans in settings["ORDER_TRANSITIONS"]:
                    if legacy_trans["source"] == trans["source"]:
                        trans.update(legacy_trans)
                        break
                else:
                    settings["ORDER_TRANSITIONS"].append(legacy_trans)

        # Save current setup into database.
        with MetaSaver(db=db) as saver:
            saver.set_id("order_statuses")
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        logging.info("saved order statuses to database")

    # Lookup for the enabled statuses.
    settings["ORDER_STATUSES_LOOKUP"] = dict(
        [(s["identifier"], s) for s in settings["ORDER_STATUSES"] if s.get("enabled")]
    )

    # Find the initial status: Ensure that there is one and only one.
    initial = None
    for status in settings["ORDER_STATUSES_LOOKUP"].values():
        if status.get("initial"):
            if initial:
                status.pop("initial")
            else:
                initial = status

    # No initial state defined; set 'preparation' to be it.
    if initial is None:
        initial = settings["ORDER_STATUSES_LOOKUP"][constants.PREPARATION]
        initial["initial"] = True
        # Save modified setup into database.
        # The doc was either retrieved or already saved above.
        with StatusSaver(doc, db=db):
            pass
        logging.info(
            "saved order statuses to database after setting 'preparation' to initial"
        )

    settings["ORDER_STATUS_INITIAL"] = initial


class TextSaver(saver.Saver):
    doctype = constants.TEXT


def load_init_texts(db):
    "Load the default texts if not already in the database."
    loaded = False
    for name in constants.TEXTS:
        if len(list(db.view("text", "name", key=name))) == 0:
            with TextSaver(db=db) as saver:
                saver["name"] = name
                saver["text"] = INIT_TEXTS.get(name, "")
            loaded = True
    if loaded:
        logging.info("loaded initial text(s)")



class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        mod_settings = settings.copy()
        # Add the root dir
        mod_settings["ROOT"] = constants.ROOT
        # Hide sensitive data.
        for key in settings:
            if "PASSWORD" in key or "SECRET" in key:
                mod_settings[key] = "<hidden>"
        # Do not show the email password.
        if mod_settings["EMAIL"].get("PASSWORD"):
            mod_settings["EMAIL"]["PASSWORD"] = "<hidden>"
        # Don't show the password in the CouchDB URL
        url = settings["DATABASE_SERVER"]
        match = re.search(r":([^/].+)@", url)
        if match:
            url = list(url)
            url[match.start(1) : match.end(1)] = "password"
            mod_settings["DATABASE_SERVER"] = "".join(url)
        mod_settings[
            "ACCOUNT_MESSAGES"
        ] = f"<see file {mod_settings['ACCOUNT_MESSAGES_FILE']}>"
        mod_settings["COUNTRIES"] = f"<see file {mod_settings['COUNTRY_CODES_FILE']}>"
        mod_settings[
            "COUNTRIES_LOOKUP"
        ] = f"<computed from file {mod_settings['COUNTRY_CODES_FILE']}>"
        mod_settings[
            "ORDER_MESSAGES"
        ] = f"<see file {mod_settings['ORDER_MESSAGES_FILE']}>"
        mod_settings[
            "ORDER_MESSAGES"
        ] = f"<see file {mod_settings['ORDER_MESSAGES_FILE']}>"
        mod_settings["ORDER_STATUSES"] = "<see page Admin -> Order statuses>"
        mod_settings["ORDER_STATUSES_LOOKUP"] = "<computed from ORDER_STATUSES}>"
        mod_settings["ORDER_TRANSITIONS"] = "<see page Admin -> Order statuses>"
        self.render("settings.html", settings=mod_settings)


class Text(RequestHandler):
    "Edit page for information text."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        try:
            text = self.get_entity_view("text", "name", name)
        except tornado.web.HTTPError:
            text = dict(name=name)
        origin = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.render("text.html", text=text, origin=origin)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        try:
            text = self.get_entity_view("text", "name", name)
        except tornado.web.HTTPError:
            text = dict(name=name)
        with TextSaver(doc=text, rqh=self) as saver:
            saver["text"] = self.get_argument("text")
        url = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.redirect(url, status=303)


class Texts(RequestHandler):
    "Page listing texts used in the web site."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("texts.html", texts=sorted(constants.TEXTS.items()))


class OrderStatuses(RequestHandler):
    "Page displaying currently defined order statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view(
            "order", "status", group_level=1, startkey=[""], endkey=[constants.CEILING]
        )
        counts = dict([(r.key[0], r.value) for r in view])
        self.render("admin_order_statuses.html", counts=counts)


class AdminOrderMessages(RequestHandler):
    "Page for displaying order messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_order_messages.html")


class AdminAccountMessages(RequestHandler):
    "Page for displaying account messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_account_messages.html")
