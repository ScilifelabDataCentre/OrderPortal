"Admin pages."

import copy
import json
import logging
import os.path
import re

import couchdb2
import tornado.web
import yaml

import orderportal
from orderportal import constants, settings, parameters
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler


DEFAULT_ORDER_STATUSES = [
    dict(
        identifier=constants.PREPARATION, # Hard-wired! Must be present and enabled.
        enabled=True,
        description="The order has been created and is being edited by the user.",
        edit=["user", "staff", "admin"],
        attach=["user", "staff", "admin"],
        action="Prepare",
    ),
    dict(
        identifier=constants.SUBMITTED, # Hard-wired! Must be present and enabled.
        enabled=True,
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
        description="The order has been cancelled.",
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
    dict(
        identifier="undefined",
        description="The order has an undefined or unknown status.",
        edit=["admin"],
        attach=["admin"],
        action="Undefine",
    ),
]


# Minimal, since only 'preparation' and 'submitted' are guaranteed to be enabled.
DEFAULT_ORDER_TRANSITIONS = dict([(s["identifier"], dict())
                                  for s in DEFAULT_ORDER_STATUSES])
DEFAULT_ORDER_TRANSITIONS[constants.PREPARATION][constants.SUBMITTED] = \
    dict(permission=["admin", "staff", "user"], require_valid=True)


DEFAULT_TEXTS_DISPLAY = [
    dict(name="header",
         description="Header on portal home page.",
         text="""This is a portal for placing orders. You need to have an account and
be logged in to create, edit, submit and view orders."""),
    dict(name="register",
         description="Registration page.",
         text="""In order to place orders, you must have registered an account in this system.
Your email address is the account name in this portal.

The administrator of the portal will review your account details,
and enable the account if everything seems fine.

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
"""),
    dict(
        name="registered",
        description="Page after registration.",
        text="""An activation email will be sent to you from the administrator
when your account has been enabled. This may take some time.
"""),
    dict(
        name="reset",
        description="Password reset page.",
        text="""Use this page to reset your password. 

An email with a link to a page for setting a new password will be sent
to you. **This may take a couple of minutes! Check your spam filter.**

The email contains a one-time code for setting a new password, and a link
to the relevant page. If you loose this code, simply do reset again.
"""),
    dict(
        name="password",
        description="Password setting page.",
        text="""Set the password for your account. You need the one-time code which
was contained in the URL sent to you by email. **Note that it takes a couple
of minutes for the email to reach you.**

If the code does not work, it may have been overwritten or already been used.
Go to [the reset page](/reset) to obtain a new code.
"""),
    dict(
        name="general",
        description="General information on portal home page.",
        text="[Add general information about the facility.]"),
    dict(
        name="contact",
        description="Contact page.",
        text="[Add information on how to contact the facility.]"),
    dict(
        name="about",
        description="About us page.",
        text="[Add information about this site.]"),
    dict(
        name="alert",
        description="Alert text at the top of every page.",
        text="**NOTE**: This site has not yet been configured."),
    dict(
        name="privacy_policy",
        description="Privacy policy statement; GDPR, etc.",
        text="""### Privacy policy (GDPR)

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
"""),
]


class MetaSaver(saver.Saver):
    doctype = constants.META

    def set_id(self, id):
        if id in constants.BANNED_META_IDS:
            raise ValueError(f"trying to use a banned meta document name '{id}'")
        self.doc["_id"] = id

    def log(self):
        "Don't bother recording log for meta documents."
        pass


def update_meta_documents(db):
    """Update or delete meta documents for the current version.
    This has to be checked each time the server starts because
    the database may have been loaded with data from an old dump.
    """

    ### As of version 6.0 (or thereabouts), there are no longer any global modes.
    ### Delete document 'global_modes' if present.
    try:
        db.delete("global_modes")
    except couchdb2.NotFoundError:
        pass

    ### As of version 6.0, the order statuses data is kept in a meta document
    ### in the database. It is no longer read from the file in
    ### the 'site' directory specified in 'settings.yaml'.
    if "order_statuses" not in db:

        # If the 'order_statuses' document is not in the database, then create it.
        # Start with the default setup.
        # If the legacy site YAML files exist, use those to update.
        # Finally save it to the database.

        # Initialize with default order statuses.
        parameters["ORDER_STATUSES"] = copy.deepcopy(DEFAULT_ORDER_STATUSES)
        lookup = dict([(p["identifier"], p) for p in parameters["ORDER_STATUSES"]])

        # Load the legacy site ORDER_STATUSES_FILE, if any defined.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_STATUSES_FILE"])
            with open(filepath) as infile:
                legacy_statuses = yaml.safe_load(infile)
            logging.info(f"loaded legacy order statuses from file '{filepath}'")
        except KeyError:
            logging.warning(f"defaults used for order statuses")
        except FileNotFoundError as error:
            logging.warning(f"defaults used for order statuses; {error}")
        else:
            # Transfer order status data from the legacy setup and flag as enabled.
            lookup = dict([(p["identifier"], p) for p in parameters["ORDER_STATUSES"]])
            for status in legacy_statuses:
                try:
                    lookup[status["identifier"]].update(status)
                    lookup[status["identifier"]]["enabled"] = True
                except KeyError:
                    logging.error(
                        f"""unknown legacy order status: '{status["identifier"]}'; skipped"""
                    )

        # Initialize with the default order transitions.
        parameters["ORDER_TRANSITIONS"] = copy.deepcopy(DEFAULT_ORDER_TRANSITIONS)

        # Load the legacy site ORDER_TRANSITIONS_FILE, if any defined.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_TRANSITIONS_FILE"])
            with open(filepath) as infile:
                legacy_transitions = yaml.safe_load(infile)
            logging.info(f"loaded legacy order transitions from file '{filepath}'")
        except KeyError:
            logging.warning(f"defaults used for order transitions")
        except FileNotFoundError as error:
            logging.warning(f"defaults used for order transitions; {error}")
        else:
            # Transfer order transitions data from legacy setup.
            # NOTE: the legacy setup had a different layout.
            for legacy_trans in legacy_transitions:
                # Skip any unknown source statuses.
                if legacy_trans["source"] not in lookup: continue
                for target in legacy_trans["targets"]:
                    # Skip any unknown target statuses.
                    if target not in lookup: continue
                    value = dict(permission=legacy_trans["permission"])
                    if legacy_trans.get("require") == "valid":
                        value["require_valid"] = True
                    parameters["ORDER_TRANSITIONS"][legacy_trans["source"]][target] = value

        initial = None
        for status in parameters["ORDER_STATUSES"]:
            if status.get("initial"):
                if initial:         # There must one and only one initial status.
                    status.pop("initial")
                else:
                    initial = status
        if initial is None:   # Set the status PREPARATION to initial, if none defined.
            lookup[constants.PREPARATION]["status"] = True

        # Save current setup into database.
        with MetaSaver(db=db) as saver:
            saver.set_id("order_statuses")
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        logging.info("saved order statuses to database")

    ### As of version 7.0, the layout of the transitions data ha been changed
    ### to a dict having (key: source status, value: dict of target statues
    ### with valid flag (instead of "require" key) and permissions list.
    doc = db["order_statuses"]
    parameters["ORDER_STATUSES"] = doc["statuses"]
    parameters["ORDER_TRANSITIONS"] = doc["transitions"]
    if isinstance(parameters["ORDER_TRANSITIONS"], list):
        new = dict([(s["identifier"], dict()) for s in parameters["ORDER_STATUSES"]])
        for trans in parameters["ORDER_TRANSITIONS"]:
            for target in trans["targets"]:
                value = dict(permission=trans["permission"])
                if trans.get("require") == "valid":
                    value["require_valid"] = True
                new[trans["source"]][target] = value
        parameters["ORDER_TRANSITIONS"] = new

        # Save current setup into database.
        with MetaSaver(doc=doc, db=db) as saver:
            saver.set_id("order_statuses")
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        logging.info("saved updated order transitions to database")

    # As of version 7.0.3, the list of order statuses to show in
    # the order list is stored in the database, not in the settings file.
    if "orders_list" not in db:
        with MetaSaver(db=db) as saver:
            saver.set_id("orders_list")
            saver["tags"] = settings.get("ORDERS_LIST_TAGS", False)
            saver["statuses"] = settings.get("ORDERS_LIST_STATUSES", list())
            # This was screwed up before version 7.0.8
            saver["fields"] = [d["identifier"] for d in settings.get("ORDERS_LIST_FIELDS", list())]
            saver["max_most_recent"] = settings.get("DISPLAY_ORDERS_MOST_RECENT", 500)
            saver["default_order_column"] = "modified"
            saver["default_order_sort"] = "desc"
        doc = saver.doc
        logging.info("saved orders list parameters to database")


class TextSaver(saver.Saver):
    doctype = constants.TEXT

    def log(self):
        "Don't bother recording log for text documents."
        pass


def update_text_documents(db):
    """Update text documents for the current version of the system.
    Remove old multiple texts; clean up after previous bug.
    Load the default texts if not already in the database.
    This has to be checked each time the server starts because
    the database may have been loaded with data from an old dump.
    """
    loaded = False
    for text in DEFAULT_TEXTS_DISPLAY:
        docs = [row.doc for row in
                db.view("text", "name", key=text["name"], include_docs=True)]
        if len(docs) == 0:       # No document in db; add it from defaults.
            with TextSaver(db=db) as saver:
                saver["type"] = constants.DISPLAY
                saver["name"] = text["name"]
                saver["description"] = text["description"]
                saver["text"] = text["text"]
            loaded = True
        elif len(docs) > 1:
            newest = docs[0]     # Deal with the consequence of a previous mistake.
            for doc in docs[1:]: # When more than one copy, then remove the older ones.
                if doc["modified"] > newest["modified"]:
                    newest = doc
            for doc in docs:
                if doc != newest:
                    db.delete(doc)
    if loaded:
        logging.info("loaded default display text(s)")

    ### As of version 7.0.4, the one-line description of a text is in the document.
    ### Defensive; This may have been done above, but not for certain.
    for text in DEFAULT_TEXTS_DISPLAY:
        docs = [row.doc for row in
                db.view("text", "name", key=text["name"], include_docs=True)]
        doc = docs[0]
        if "description" not in doc: # Update to version 7.0.4
            with TextSaver(doc, db=db) as saver:
                saver["type"] = constants.DISPLAY
                saver["description"] = text["description"]


def load_texts(db):
    "Load the texts into parameters."
    for type in [constants.DISPLAY, constants.ACCOUNT, constants.ORDER]:
        parameters[type] = dict()
        for row in db.view("text", "type", key=type, include_docs=True):
            parameters[type][row.doc["name"]] = row.doc


class Texts(RequestHandler):
    "Page listing texts used in the web site."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        texts = []
        for type in [constants.DISPLAY, constants.ACCOUNT, constants.ORDER]:
            texts.extend(sorted(parameters[type].values(), key=lambda d: d["name"]))
        self.render("admin_texts.html", texts=texts)


class TextEdit(RequestHandler):
    "Edit page for text."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        try:
            text = parameters[constants.DISPLAY][name]
        except KeyError:
            text = dict(name=name)
        # Go back to display page showing the text, if given.
        origin = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.render("admin_text_edit.html", text=text, origin=origin)

    @tornado.web.authenticated
    def post(self, name):
        "Save the modified text to the database, and update parameters."
        self.check_admin()
        doc = self.get_entity_view("text", "name", name)
        text = self.get_argument("text", "")
        with TextSaver(doc=doc, rqh=self) as saver:
            saver["text"] = text
        parameters[doc["type"]][doc["name"]]["text"] = text
        url = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.redirect(url, status=303)


def load_parameters(db):
    """Load the parameters from the database:
    - order statuses and transitions
    - orders list parameters
    and setup derived variable values.
    """
    doc = db["order_statuses"]
    parameters["ORDER_STATUSES"] = doc["statuses"]
    parameters["ORDER_TRANSITIONS"] = doc["transitions"]
    logging.info("loaded order statuses from database into 'parameters'")

    doc = db["orders_list"]
    parameters["ORDERS_LIST_TAGS"] = doc["tags"]
    parameters["ORDERS_LIST_STATUSES"] = doc["statuses"]
    parameters["ORDERS_LIST_FIELDS"] = doc["fields"]
    parameters["DISPLAY_ORDERS_MOST_RECENT"] = doc["max_most_recent"]
    parameters["DEFAULT_ORDER_COLUMN"] = doc["default_order_column"]
    parameters["DEFAULT_ORDER_SORT"] = doc["default_order_sort"]
    logging.info("loaded orders list parameters from database into 'parameters'")

    # Lookup for the enabled statuses.
    parameters["ORDER_STATUSES_LOOKUP"] = dict(
        [(s["identifier"], s)
         for s in parameters["ORDER_STATUSES"] if s.get("enabled")]
    )

    # Find the initial status.
    for status in parameters["ORDER_STATUSES"]:
        if status.get("initial"):
            parameters["ORDER_STATUS_INITIAL"] = status


class OrderStatuses(RequestHandler):
    "Page displaying currently defined order statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        enabled = [s for s in parameters["ORDER_STATUSES"] if s.get("enabled")]
        not_enabled = [s for s in parameters["ORDER_STATUSES"] if not s.get("enabled")]
        targets = {}
        for source, transitions in parameters["ORDER_TRANSITIONS"].items():
            for target, transition in transitions.items():
                targets.setdefault(target, {})[source] = transition
        view = self.db.view(
            "order", "status", group_level=1, startkey=[""], endkey=[constants.CEILING]
        )
        counts = dict([(r.key[0], r.value) for r in view])
        self.render("admin_order_statuses.html",
                    enabled=enabled,
                    not_enabled=not_enabled,
                    sources=parameters["ORDER_TRANSITIONS"],
                    targets=targets,
                    counts=counts)


class OrderStatusEnable(RequestHandler):
    "Enable an order status."

    @tornado.web.authenticated
    def post(self, status_id):
        self.check_admin()
        for status in parameters["ORDER_STATUSES"]:
            if status["identifier"] == status_id: break
        else:
            self.see_other("admin_order_statuses", error="No such order status.")
            return
        status["enabled"] = True
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        load_parameters(self.db)
        self.see_other("admin_order_statuses")
        

class OrderStatusEdit(RequestHandler):
    "Edit an order status."

    @tornado.web.authenticated
    def get(self, status_id):
        self.check_admin()
        try:
            status = parameters["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
        else:
            self.render("admin_order_status_edit.html", status=status)

    @tornado.web.authenticated
    def post(self, status_id):
        self.check_admin()
        try:
            status = parameters["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
            return
        status["description"] = self.get_argument("description", "").strip()
        initial = utils.to_bool(self.get_argument("initial", False))
        # Only one status may be initial; set all others to False.
        if initial and not status.get("initial"):
            for s in parameters["ORDER_STATUSES_LOOKUP"].values():
                s["initial"] = False
            status["initial"] = True
        status["edit"] = ["admin"] # Is always allowed.
        if utils.to_bool(self.get_argument("edit_staff", False)):
            status["edit"].append("staff")
        if utils.to_bool(self.get_argument("edit_user", False)):
            status["edit"].append("user")
        status["attach"] = ["admin"] # Is always allowed.
        if utils.to_bool(self.get_argument("attach_staff", False)):
            status["attach"].append("staff")
        if utils.to_bool(self.get_argument("attach_user", False)):
            status["attach"].append("user")
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        load_parameters(self.db)
        self.see_other("admin_order_statuses")


class OrderTransitionsEdit(RequestHandler):
    "Edit the allowed transitions of an order."

    @tornado.web.authenticated
    def get(self, status_id):
        self.check_admin()
        try:
            status = parameters["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
        else:
            targets = parameters["ORDER_TRANSITIONS"].get(status_id, dict())
            # Defensive: only allow enabled statuses as targets.
            for target in targets.keys():
                if target not in parameters["ORDER_STATUSES_LOOKUP"]:
                    targets.pop(target)
            new_targets = [t for t in parameters["ORDER_STATUSES_LOOKUP"].keys()
                           if t != status_id]
            self.render("admin_order_transitions_edit.html",
                        status=status,
                        targets=targets,
                        new_targets=new_targets)

    @tornado.web.authenticated
    def post(self, status_id):
        self.check_admin()
        if self.get_argument("_http_method", None) == "delete":
            self.delete(status_id)
            return
        try:
            source = parameters["ORDER_STATUSES_LOOKUP"][status_id]
            target = parameters["ORDER_STATUSES_LOOKUP"][self.get_argument("target")]
        except (tornado.web.MissingArgumentError, KeyError):
            self.see_other("admin_order_statuses", error="Invalid or missing order status.")
            return
        permission = self.get_arguments("permission")
        if not permission:
            self.see_other("admin_order_statuses", error="No permissions specified.")
            return
        value = dict(permission=permission)
        if utils.to_bool(self.get_argument("require_valid", False)):
            value["require_valid"] = True
        parameters["ORDER_TRANSITIONS"][source["identifier"]][target["identifier"]] = value
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        load_parameters(self.db)
        self.see_other("admin_order_statuses")

    @tornado.web.authenticated
    def delete(self, status_id):
        try:
            source = parameters["ORDER_STATUSES_LOOKUP"][status_id]
            target = parameters["ORDER_STATUSES_LOOKUP"][self.get_argument("target")]
            parameters["ORDER_TRANSITIONS"][source["identifier"]].pop(target["identifier"])
        except (tornado.web.MissingArgumentError, KeyError):
            self.see_other("admin_order_statuses", error="Invalid or missing order status.")
            return
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = parameters["ORDER_STATUSES"]
            saver["transitions"] = parameters["ORDER_TRANSITIONS"]
        load_parameters(self.db)
        self.see_other("admin_order_statuses")


class OrdersList(RequestHandler):
    "Display orders list parameters."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_orders_list.html")


class OrdersListEdit(RequestHandler):
    "Edit orders list parameters."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_orders_list_edit.html")

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with MetaSaver(doc=self.db["orders_list"], rqh=self) as saver:
            saver["tags"] = utils.to_bool(self.get_argument("orders_list_tags", False))
            saver["statuses"] = [s for s in self.get_arguments("orders_list_statuses")
                                 if s in parameters["ORDER_STATUSES_LOOKUP"]]
            saver["fields"] = self.get_argument("orders_list_fields", "").strip().split()
            try:
                value = int(self.get_argument("orders_most_recent"))
                if value < 10:
                    raise ValueError
                saver["max_most_recent"] = value
            except (tornado.web.MissingArgumentError, ValueError, TypeError):
                pass
            value = self.get_argument("default_order_column", "-").lower()
            if value == "identifier":
                saver["default_order_column"] = "identifier"
            else:
                saver["default_order_column"] = "modified"
            value = self.get_argument("default_order_sort", "-").lower()
            if value == "asc":
                saver["default_order_sort"] = "asc"
            else:
                saver["default_order_sort"] = "desc"
        load_parameters(self.db)
        self.see_other("admin_orders_list")


class OrderMessages(RequestHandler):
    "Page for displaying order messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_order_messages.html")


class AccountMessages(RequestHandler):
    "Page for displaying account messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin_account_messages.html")


class Database(RequestHandler):
    "Page displaying info about the database."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        server = utils.get_dbserver()
        self.render("admin_database.html",
                    doc=utils.get_document(self.db, self.get_argument("identifier", "")),
                    counts=utils.get_counts(self.db),
                    db_info=self.db.get_info(),
                    server_data=server(),
                    databases=list(server),
                    system_stats=server.get_node_system(),
                    node_stats=server.get_node_stats())

class Document(RequestHandler):
    "Download a document from the CouchDB database."

    @tornado.web.authenticated
    def get(self, id):
        self.check_admin()
        try:
            doc = self.db[id]
        except couchdb2.NotFoundError:
            return self.see_other("admin_database")
        self.set_header("Content-Type", constants.JSON_MIME)
        self.set_header("Content-Disposition", f'attachment; filename="{id}.json"')
        self.write(json.dumps(doc, indent=2))


class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        hidden = "&lt;hidden&gt;"
        mod_settings = settings.copy()
        # Add the root dir
        mod_settings["ROOT"] = constants.ROOT
        # Hide sensitive data.
        for key in settings:
            if "PASSWORD" in key or "SECRET" in key:
                mod_settings[key] = hidden
        # Do not show the email password.
        if mod_settings["EMAIL"].get("PASSWORD"):
            mod_settings["EMAIL"]["PASSWORD"] = hidden
        # Don't show the password in the CouchDB URL; actually obsolete now...
        url = settings["DATABASE_SERVER"]
        match = re.search(r":([^/].+)@", url)
        if match:
            url = list(url)
            url[match.start(1) : match.end(1)] = "password"
            mod_settings["DATABASE_SERVER"] = "".join(url)
        mod_settings[
            "ACCOUNT_MESSAGES"
        ] = f"&lt;see file {mod_settings['ACCOUNT_MESSAGES_FILE']}&gt;"
        mod_settings["COUNTRIES"] = f"&lt;see file {mod_settings['COUNTRY_CODES_FILE']}&gt;"
        mod_settings[
            "COUNTRIES_LOOKUP"
        ] = f"&lt;computed from file {mod_settings['COUNTRY_CODES_FILE']}&gt;"
        mod_settings[
            "ORDER_MESSAGES"
        ] = f"&lt;see file {mod_settings['ORDER_MESSAGES_FILE']}%gt;"
        mod_settings[
            "ORDER_MESSAGES"
        ] = f"&lt;see file {mod_settings['ORDER_MESSAGES_FILE']}&gt;"
        for obsolete in ["ORDER_STATUSES_FILE", 
                         "ORDER_TRANSITIONS_FILE",
                         "ORDERS_LIST_TAGS",
                         "ORDERS_LIST_STATUSES",
                         "ORDERS_LIST_FIELDS",
                         "DISPLAY_ORDERS_MOST_RECENT",
                         "SITE_PERSONAL_DATA_POLICY"]:
            if obsolete in mod_settings:
                mod_settings[obsolete] = " &lt;<b>OBSOLETE; NO LONGER USED</b>&gt;"
        self.render("admin_settings.html", settings=mod_settings)
