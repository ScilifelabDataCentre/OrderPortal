"Admin pages."

import copy
import email.message
import json
import logging
import os
import os.path
import re
import smtplib

import couchdb2
import tornado.web
import yaml

import orderportal
from orderportal import constants, DEFAULT_SETTINGS, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler
import orderportal.config
import orderportal.database


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
    logger = logging.getLogger("orderportal")
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
        settings["ORDER_STATUSES"] = copy.deepcopy(DEFAULT_ORDER_STATUSES)
        lookup = dict([(p["identifier"], p) for p in settings["ORDER_STATUSES"]])

        # Load the legacy site ORDER_STATUSES_FILE, if any defined.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_STATUSES_FILE"])
            with open(filepath) as infile:
                legacy_statuses = yaml.safe_load(infile)
            logger.info(f"loaded legacy order statuses from file '{filepath}'")
        except KeyError:
            logger.warning(f"defaults used for order statuses")
        except FileNotFoundError as error:
            logger.warning(f"defaults used for order statuses; {error}")
        except yaml.YAMLError as error:
            logger.warning(f"Error trying to read ORDER_STATUSES_FILE: {error}")
        else:
            # Transfer order status data from the legacy setup and flag as enabled.
            lookup = dict([(p["identifier"], p) for p in settings["ORDER_STATUSES"]])
            for status in legacy_statuses:
                try:
                    lookup[status["identifier"]].update(status)
                    lookup[status["identifier"]]["enabled"] = True
                except KeyError:
                    logger.error(
                        f"""unknown legacy order status: '{status["identifier"]}'; skipped"""
                    )

        # Initialize with the default order transitions.
        settings["ORDER_TRANSITIONS"] = copy.deepcopy(DEFAULT_ORDER_TRANSITIONS)

        # Load the legacy site ORDER_TRANSITIONS_FILE, if any defined.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_TRANSITIONS_FILE"])
            with open(filepath) as infile:
                legacy_transitions = yaml.safe_load(infile)
            logger.info(f"loaded legacy order transitions from file '{filepath}'")
        except KeyError:
            logger.warning(f"defaults used for order transitions")
        except FileNotFoundError as error:
            logger.warning(f"defaults used for order transitions; {error}")
        except yaml.YAMLError as error:
            logger.warning(f"Error trying to read ORDER_TRANSITIONS_FILE: {error}")
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
                    settings["ORDER_TRANSITIONS"][legacy_trans["source"]][target] = value

        initial = None
        for status in settings["ORDER_STATUSES"]:
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
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        logger.info("saved order statuses to database")

    ### As of version 7.0, the layout of the transitions data ha been changed
    ### to a dict having (key: source status, value: dict of target statues
    ### with valid flag (instead of "require" key) and permissions list.
    doc = db["order_statuses"]
    settings["ORDER_STATUSES"] = doc["statuses"]
    settings["ORDER_TRANSITIONS"] = doc["transitions"]
    if isinstance(settings["ORDER_TRANSITIONS"], list):
        new = dict([(s["identifier"], dict()) for s in settings["ORDER_STATUSES"]])
        for trans in settings["ORDER_TRANSITIONS"]:
            for target in trans["targets"]:
                value = dict(permission=trans["permission"])
                if trans.get("require") == "valid":
                    value["require_valid"] = True
                new[trans["source"]][target] = value
        settings["ORDER_TRANSITIONS"] = new

        # Save current setup into database.
        with MetaSaver(doc=doc, db=db) as saver:
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        logger.info("saved updated order transitions to database")

    # As of version 7.0.3, items to show in the order list is stored
    # in the database, not in the settings file.
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
        logger.info("saved orders list settings to database")

    # Re-introduce order list filters, this time separately from orders list fields.
    doc = db["orders_list"]
    if "filters" not in doc:
        with MetaSaver(doc=doc, db=db) as saver:
            saver["filters"] = []


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
        # Due to the problem lower down, have to use a bespoke docs fetch here.
        docs = [row.doc for row in db.view("text", "name", key=text["name"],
                                           reduce=False, include_docs=True)]
        if len(docs) == 0:       # No document in db; add it from defaults.
            with TextSaver(db=db) as saver:
                saver["type"] = constants.DISPLAY
                saver["name"] = text["name"]
                saver["description"] = text["description"]
                saver["text"] = text["text"]
            loaded = True
        elif len(docs) == 1:
            if not docs[0].get("type"): # Fix previous mistake.
                with TextSaver(doc=docs[0], db=db) as saver:
                    saver["type"] = constants.DISPLAY
        elif len(docs) > 1:
            newest = docs[0]     # Deal with the consequence of a previous mistake.
            for doc in docs[1:]: # When more than one copy, then remove the older ones.
                if doc["modified"] > newest["modified"]:
                    newest = doc
            for doc in docs:
                if doc != newest:
                    db.delete(doc)
            if not newest.get("type"):
                with TextSaver(doc=newest, db=db) as saver:
                    saver["type"] = constants.DISPLAY
    if loaded:
        logging.getLogger("orderportal").info("loaded default display text(s)")

    ### As of version 7.0.4, the one-line description of a text is in the document.
    ### Defensive; This may have been done above, but not for certain.
    docs = [row.doc for row in db.view("text", "type", constants.DISPLAY,
                                       include_docs=True)]
    lookup = dict([(d["name"], d) for d in docs])
    for text in DEFAULT_TEXTS_DISPLAY:
        try:
            doc = lookup[text["name"]]
        except KeyError:
            pass
        else:
            if "description" not in doc: # Update to version 7.0.4
                with TextSaver(doc, db=db) as saver:
                    saver["type"] = constants.DISPLAY
                    saver["description"] = text["description"]

    ### As of version 7.0.11, the message templates for emails about account
    ### status changes are stored in the database as texts.
    ### NOTE: The account messages YAML file is ignored! It is unlikely
    ### to have been customized by anyone. The default is used.
    docs = [row.doc for row in db.view("text", "type", constants.ACCOUNT,
                                       include_docs=True)]
    lookup = dict([(d["status"], d) for d in docs])
    loaded = False
    for text in DEFAULT_TEXTS_ACCOUNT:
        if text["status"] not in lookup:
            with TextSaver(db=db) as saver:
                saver["type"] = constants.ACCOUNT
                saver["name"] = text["status"] # Yes, the status only.
                saver["status"] = text["status"]
                saver["description"] = text["description"]
                saver["recipients"] = text["recipients"]
                saver["subject"] = text["subject"]
                saver["text"] = text["text"]
            loaded = True


def load_texts(db):
    "Load the texts into settings."
    for type in [constants.DISPLAY, constants.ACCOUNT, constants.ORDER]:
        docs = [row.doc for row in db.view("text", "type", type, include_docs=True)]
        settings[type] = dict()
        for doc in docs:
            settings[type][doc["name"]] = doc


class Texts(RequestHandler):
    "Page listing texts used in the web site."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin/texts.html", texts=self.get_texts(constants.DISPLAY))


class TextEdit(RequestHandler):
    "Edit page for display text."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        try:
            text = settings[constants.DISPLAY][name]
        except KeyError:
            text = dict(name=name)
        # Go back to display page showing the text, if given.
        origin = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.render("admin/text_edit.html", text=text, origin=origin)

    @tornado.web.authenticated
    def post(self, name):
        "Save the modified text to the database, and update settings."
        self.check_admin()
        try:
            doc = self.get_text(constants.DISPLAY, name)
        except KeyError:
            raise tornado.web.HTTPError(404, reason="No such text.")
        text = self.get_argument("text", "")
        with TextSaver(doc=doc, rqh=self) as saver:
            saver["text"] = text
        settings[doc["type"]][doc["name"]]["text"] = text
        url = self.get_argument("origin", self.absolute_reverse_url("texts"))
        self.redirect(url, status=303)


class OrderStatuses(RequestHandler):
    "Page displaying currently defined order statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        enabled = [s for s in settings["ORDER_STATUSES"] if s.get("enabled")]
        not_enabled = [s for s in settings["ORDER_STATUSES"] if not s.get("enabled")]
        targets = {}
        for source, transitions in settings["ORDER_TRANSITIONS"].items():
            for target, transition in transitions.items():
                targets.setdefault(target, {})[source] = transition
        view = self.db.view(
            "order", "status", group_level=1, startkey=[""], endkey=[constants.CEILING]
        )
        counts = dict([(r.key[0], r.value) for r in view])
        self.render("admin/order_statuses.html",
                    enabled=enabled,
                    not_enabled=not_enabled,
                    sources=settings["ORDER_TRANSITIONS"],
                    targets=targets,
                    counts=counts)


class OrderStatusEnable(RequestHandler):
    "Enable an order status."

    @tornado.web.authenticated
    def post(self, status_id):
        self.check_admin()
        for status in settings["ORDER_STATUSES"]:
            if status["identifier"] == status_id: break
        else:
            self.see_other("admin_order_statuses", error="No such order status.")
            return
        status["enabled"] = True
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        orderportal.config.load_settings_from_db(self.db)
        self.see_other("admin_order_statuses")
        

class OrderStatusEdit(RequestHandler):
    "Edit an order status."

    @tornado.web.authenticated
    def get(self, status_id):
        self.check_admin()
        try:
            status = settings["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
        else:
            self.render("admin/order_status_edit.html", status=status)

    @tornado.web.authenticated
    def post(self, status_id):
        self.check_admin()
        try:
            status = settings["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
            return
        value = self.get_argument("description", "").strip()
        if value:
            status["description"] = value
        else:
            self.set_error_flash("There must be a description; not changed.")
        initial = utils.to_bool(self.get_argument("initial", False))
        # Only one status may be initial; set all others to False.
        if initial and not status.get("initial"):
            for s in settings["ORDER_STATUSES_LOOKUP"].values():
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
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        orderportal.config.load_settings_from_db(self.db)
        self.see_other("admin_order_statuses")


class OrderTransitionsEdit(RequestHandler):
    "Edit the allowed transitions of an order."

    @tornado.web.authenticated
    def get(self, status_id):
        self.check_admin()
        try:
            status = settings["ORDER_STATUSES_LOOKUP"][status_id]
        except KeyError:
            self.see_other("admin_order_statuses", error="No such order status.")
        else:
            targets = settings["ORDER_TRANSITIONS"].get(status_id, dict())
            # Defensive: only allow enabled statuses as targets.
            for target in targets.keys():
                if target not in settings["ORDER_STATUSES_LOOKUP"]:
                    targets.pop(target)
            new_targets = [t for t in settings["ORDER_STATUSES_LOOKUP"].keys()
                           if t != status_id]
            self.render("admin/order_transitions_edit.html",
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
            source = settings["ORDER_STATUSES_LOOKUP"][status_id]
            target = settings["ORDER_STATUSES_LOOKUP"][self.get_argument("target")]
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
        settings["ORDER_TRANSITIONS"][source["identifier"]][target["identifier"]] = value
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        orderportal.config.load_settings_from_db(self.db)
        self.see_other("admin_order_statuses")

    @tornado.web.authenticated
    def delete(self, status_id):
        try:
            source = settings["ORDER_STATUSES_LOOKUP"][status_id]
            target = settings["ORDER_STATUSES_LOOKUP"][self.get_argument("target")]
            settings["ORDER_TRANSITIONS"][source["identifier"]].pop(target["identifier"])
        except (tornado.web.MissingArgumentError, KeyError):
            self.see_other("admin_order_statuses", error="Invalid or missing order status.")
            return
        with MetaSaver(doc=self.db["order_statuses"], rqh=self) as saver:
            saver["statuses"] = settings["ORDER_STATUSES"]
            saver["transitions"] = settings["ORDER_TRANSITIONS"]
        orderportal.config.load_settings_from_db(self.db)
        self.see_other("admin_order_statuses")


class OrdersList(RequestHandler):
    "Orders list configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin/orders_list.html")

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        doc = self.db["orders_list"]
        with MetaSaver(doc=doc, rqh=self) as saver:
            saver["owner_university"] = utils.to_bool(self.get_argument("owner_university", False))
            saver["owner_department"] = utils.to_bool(self.get_argument("owner_department", False))
            if settings.get("ACCOUNT_FUNDER_INFO_GENDER"):
                saver["owner_gender"] = utils.to_bool(self.get_argument("owner_gender", False))
            saver["tags"] = utils.to_bool(self.get_argument("tags", False))
            saver["statuses"] = [s for s in self.get_arguments("statuses")
                                 if s in settings["ORDER_STATUSES_LOOKUP"]]
            saver["fields"] = self.get_argument("fields", "").strip().split()
            # Lookup of filters with identifier as key.
            filters = dict([(f["identifier"], f) for f in doc["filters"]])
            # Delete specified fields.
            for value in self.get_arguments("orders_filter_field_delete"):
                filters.pop(value, None)
            # Add a specified field.
            try:
                value = self.get_argument("orders_filter_field")
                if value:
                    value = yaml.safe_load(value)
                    if not isinstance(value, dict):
                        raise ValueError
                    filter = dict(identifier=value["identifier"],
                                  values=value["values"])
                    if not isinstance(filter["identifier"], str):
                        raise ValueError
                    if not isinstance(filter["values"], list):
                        raise ValueError
                    if len(filter["values"]) == 0:
                        raise ValueError
                    try:
                        filter["label"] = value["label"]
                    except KeyError:
                        pass
                    # Overwrite if identifier is already in the list.
                    filters[filter["identifier"]] = filter
            except (KeyError, ValueError, yaml.YAMLError):
                self.set_error_flash("Invalid YAML for 'Orders filter field'; ignored.")
            saver["filters"] =  list(filters.values())
            try:
                value = int(self.get_argument("orders_most_recent"))
                if value < 10:
                    raise ValueError
                saver["max_most_recent"] = value
            except (tornado.web.MissingArgumentError, ValueError, TypeError):
                self.set_error_flash("Invalid value for 'Max most recent'; ignored.")
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
        orderportal.config.load_settings_from_db(self.db)
        self.set_message_flash("Saved configuration.")
        self.see_other("admin_orders_list")


class OrderMessages(RequestHandler):
    "Page for displaying order messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin/order_messages.html")


class Account(RequestHandler):
    "Page for display and edit of account configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("admin/account_config.html")
    
    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        self.set_message_flash("Saved configuration.")
        self.see_other("admin_orders_list")
    

class AccountMessages(RequestHandler):
    "Page for displaying account messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        docs = [row.doc for row in self.db.view("text", "type", key=constants.ACCOUNT,
                                                 reduce=False, include_docs=True)]
        docs.sort(key=lambda t: t["status"])
        self.render("admin/account_messages.html", texts=docs)


class AccountMessageEdit(RequestHandler):
    "Page for editing an account message."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        self.render("admin/account_message_edit.html",
                    text=self.get_text(constants.ACCOUNT, name))

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        doc = self.get_text(constants.ACCOUNT, name)
        with TextSaver(doc, rqh=self) as saver:
            saver["subject"] = self.get_argument("subject", None) or "[no subject]"
            saver["recipients"] = self.get_arguments("recipients")
            saver["text"] = self.get_argument("text", None) or "[no text]"
        self.see_other("admin_account_messages")


class Database(RequestHandler):
    "Page displaying info about the database."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        server = orderportal.database.get_server()
        identifier = self.get_argument("identifier", "")
        self.render("admin/database.html",
                    identifier=identifier,
                    doc=orderportal.database.lookup_document(self.db, identifier),
                    counts=orderportal.database.get_counts(self.db),
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
        self.set_header("Content-Type", constants.JSON_MIMETYPE)
        self.set_header("Content-Disposition", f'attachment; filename="{id}.json"')
        self.write(json.dumps(doc, ensure_ascii=False, indent=2))


class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        hidden = "&lt;hidden&gt;"
        safe_settings = dict([(key, settings[key]) for key in DEFAULT_SETTINGS])

        # Hide sensitive data.
        for key in safe_settings:
            if "PASSWORD" in key or "SECRET" in key:
                safe_settings[key] = hidden

        # Escape any '<' and '>' in email addresses
        for key in ["MAIL_DEFAULT_SENDER", "MAIL_REPLY_TO"]:
            value = safe_settings[key]
            if value:
                safe_settings[key] = value.replace("<", "&lt;").replace(">", "&gt;")

        # Don't show the password in the CouchDB URL; actually obsolete now...
        url = safe_settings["DATABASE_SERVER"]
        match = re.search(r":([^/].+)@", url)
        if match:
            url = list(url)
            url[match.start(1) : match.end(1)] = "password"
            safe_settings["DATABASE_SERVER"] = "".join(url)
        safe_settings[
            "ORDER_MESSAGES"
        ] = f"&lt;see file {safe_settings['ORDER_MESSAGES_FILE']}&gt;"
        self.render("admin/settings.html", settings=safe_settings)


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


# Texts shown in some web pages.
DEFAULT_TEXTS_DISPLAY = [
    dict(name="header",
         description="Header on portal home page.",
         text="""This is a portal for placing orders. You need to have an account and
be logged in to create, edit, submit and view orders."""),
    dict(name="register",
         description="Registration page text.",
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
above."""),
    dict(
        name="registered",
        description="Text on page after registration.",
        text="""An activation email will be sent to you from the administrator
when your account has been enabled. This may take some time."""),
    dict(
        name="reset",
        description="Password reset page text.",
        text="""Use this page to reset your password. 

An email with a link to a page for setting a new password will be sent
to you. **This may take a couple of minutes! Check your spam filter.**

The email contains a one-time code for setting a new password, and a link
to the relevant page. If you loose this code, simply do reset again.
"""),
    dict(
        name="password",
        description="Password setting page text.",
        text="""Set the password for your account. You need the one-time code which
was contained in the URL sent to you by email. **Note that it takes a couple
of minutes for the email to reach you.**

If the code does not work, it may have been overwritten or already been used.
Go to [the reset page](/reset) to obtain a new code."""),
    dict(
        name="general",
        description="General information on portal home page.",
        text="[Add general information about the facility.]"),
    dict(
        name="contact",
        description="Contact page text.",
        text="[Add information on how to contact the facility.]"),
    dict(
        name="about",
        description="Text on the about us page.",
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
and orders contains the records of all changes to those items."""),
]


# Message templates for account status changes.
DEFAULT_TEXTS_ACCOUNT = [
    dict(status=constants.PENDING,
         description="Message to admin about a pending account.",
         recipients=[constants.ADMIN],
         subject="An account {account} in the {site} is pending approval.",
         text="""An account {account} in the {site} is pending approval.

Go to {url} to view and enable it.
"""),
    dict(status=constants.ENABLED,
         description="Message to user about enabled account.",
         recipients=[constants.USER],
         subject="Your account in the {site} has been enabled.",
         text="""Your account {account} in the {site} has been enabled.

However, you will first have to set your password for the account.

Go to {password_code_url} to set the password.

In case that link does not work, go to {password_url} and
fill in your email address and the one-time code {code}.

If you have any questions, contact {support}

Yours sincerely,
The {site} administrators.
"""),

    dict(status=constants.RESET,
         description="Message to user about password reset.",
         recipients=[constants.USER],
         subject="The password has been reset for your account in the {site}.",
         text="""The password has been reset for your account {account} in the {site}.

Go to {password_code_url} to set a new password.

In case that link does not work, go to {password_url} and
fill in your email address and the one-time code {code}.

If you have any questions, contact {support}

Yours sincerely,
The {site} administrators.
"""),
    dict(status=constants.DISABLED,
         description="Message to user about disabled account.",
         recipients=[constants.USER],
         subject="Your account in the {site} has been disabled.",
         text="""Your account has been disabled.
This may be due to too many recent failed login attempts.

To resolve this, please contact {support}

Yours sincerely,
The {site} administrators.
""")
]
