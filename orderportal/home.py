"Home page variants, and a few general resources."

import logging
import os.path
import sys

import couchdb2
import markdown
import requests
import tornado
import tornado.web
import xlsxwriter
import yaml

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in account."

    def get(self):

        forms = [r.doc for r in self.db.view("form", "enabled", include_docs=True)]
        for f in forms:
            if f.get("ordinal") is None:
                f["ordinal"] = 0
        forms.sort(key=lambda i: i["ordinal"])
        kwargs = dict(
            forms=forms,
            news_items=self.get_news(limit=settings["DISPLAY_MAX_NEWS"]),
            events=self.get_events(upcoming=True),
        )
        if self.current_user and self.get_invitations(self.current_user["email"]):
            url = self.reverse_url("account", self.current_user["email"])
            kwargs[
                "message"
            ] = """You have group invitations.
See your <a href="{0}">account</a>.""".format(
                url
            )
        if not self.current_user:
            self.render("home.html", **kwargs)
        elif self.current_user["role"] == constants.ADMIN:
            self.home_admin(**kwargs)
        elif self.current_user["role"] == constants.STAFF:
            self.home_staff(**kwargs)
        else:
            self.home_user(**kwargs)

    def home_admin(self, **kwargs):
        "Home page for a current user having role 'admin'."
        view = self.db.view(
            "account", "status", key=constants.PENDING, include_docs=True
        )
        pending = [r.doc for r in view]
        pending.sort(key=lambda i: i["modified"], reverse=True)
        pending = pending[: settings["DISPLAY_MAX_PENDING_ACCOUNTS"]]
        # NOTE: Hard-wired status 'submitted'!
        view = self.db.view(
            "order",
            "status",
            descending=True,
            startkey=["submitted", constants.CEILING],
            endkey=["submitted"],
            limit=settings["DISPLAY_MAX_RECENT_ORDERS"],
            reduce=False,
            include_docs=True,
        )
        orders = [r.doc for r in view]
        self.render("home_admin.html", pending=pending, orders=orders, **kwargs)

    def home_staff(self, **kwargs):
        "Home page for a current user having role 'staff'."
        # NOTE: Hard-wired status 'submitted'!
        view = self.db.view(
            "order",
            "status",
            descending=True,
            startkey=["accepted", constants.CEILING],
            endkey=["accepted"],
            limit=settings["DISPLAY_MAX_RECENT_ORDERS"],
            reduce=False,
            include_docs=True,
        )
        orders = [r.doc for r in view]
        self.render("home_staff.html", orders=orders, **kwargs)

    def home_user(self, **kwargs):
        "Home page for a current user having role 'user'."
        if not settings["ORDER_CREATE_USER"]:
            kwargs["forms"] = None  # Indicates that users can't create orders.
        view = self.db.view(
            "order",
            "owner",
            reduce=False,
            include_docs=True,
            descending=True,
            startkey=[self.current_user["email"], constants.CEILING],
            endkey=[self.current_user["email"]],
            limit=settings["DISPLAY_MAX_RECENT_ORDERS"],
        )
        orders = [r.doc for r in view]
        self.render("home_user.html", orders=orders, **kwargs)


class Status(RequestHandler):
    "Return JSON for the current status and some counts for the database."

    def get(self):
        result = dict(status="OK")
        result.update(utils.get_counts(self.db))
        self.write(result)


class Contact(RequestHandler):
    "Display contact information."

    def get(self):
        self.render("contact.html")


class About(RequestHandler):
    "Display 'About us' information."

    def get(self):
        self.render("about.html")


class Software(RequestHandler):
    "Display software information for the web site."

    def get(self):
        software = [
            ("OrderPortal", orderportal.__version__, constants.SOURCE_URL),
            ("Python", constants.PYTHON_VERSION, constants.PYTHON_URL),
            ("tornado", tornado.version, constants.TORNADO_URL),
            ("CouchDB server", self.db.server.version, constants.COUCHDB_URL),
            ("CouchDB2 interface", couchdb2.__version__, constants.COUCHDB2_URL),
            ("XslxWriter", xlsxwriter.__version__, constants.XLSXWRITER_URL),
            ("Markdown", markdown.version, constants.MARKDOWN_URL),
            ("requests", requests.__version__, constants.REQUESTS_URL),
            ("PyYAML", yaml.__version__, constants.PYYAML_URL),
            ("Bootstrap", constants.BOOTSTRAP_VERSION, constants.BOOTSTRAP_URL),
            ("jQuery", constants.JQUERY_VERSION, constants.JQUERY_URL),
            ("jQuery.UI", constants.JQUERY_UI_VERSION, constants.JQUERY_URL),
            (
                "jQuery.localtime",
                constants.JQUERY_LOCALTIME_VERSION,
                constants.JQUERY_LOCALTIME_URL,
            ),
            ("DataTables", constants.DATATABLES_VERSION, constants.DATATABLES_URL),
        ]
        self.render("software.html", software=software)


class Log(RequestHandler):
    "Singe log entry; JSON output."

    def get(self, iuid):
        log = self.get_entity(iuid, doctype=constants.LOG)
        log["iuid"] = log.pop("_id")
        log.pop("_rev")
        log.pop("orderportal_doctype")
        self.write(log)
        self.set_header("Content-Type", constants.JSON_MIME)


class Entity(RequestHandler):
    "Redirect to the entity given by the IUID, if any."

    def get(self, iuid):
        "Login and privileges are checked by the entity redirected to."
        doc = self.get_entity(iuid)
        if doc[constants.DOCTYPE] == constants.ORDER:
            self.redirect(self.order_reverse_url(doc))
        elif doc[constants.DOCTYPE] == constants.FORM:
            self.see_other("form", doc["_id"])
        elif doc[constants.DOCTYPE] == constants.ACCOUNT:
            self.see_other("account", doc["email"])
        else:
            self.see_other("home", error="Sorry, no such entity found.")


class NoSuchEntity(RequestHandler):
    "Error message on home page."

    def get(self, path=None):
        logging.debug("No such entity: %s", path)
        self.see_other("home", error="Sorry, no such entity found.")


class NoSuchEntityApiV1(RequestHandler):
    "Return Not Found status code."

    def get(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def post(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def put(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when API."
        pass
