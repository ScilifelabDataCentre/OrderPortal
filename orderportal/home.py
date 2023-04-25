"Home page variants, and a few general resources."

import os.path
import sys

import couchdb2
import marko
import requests
import tornado
import tornado.web
import xlsxwriter
import yaml

import orderportal
import orderportal.database
from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in account."

    def get(self):
        "Home page; contents depends on the role of the logged-in account, if any."
        forms = [row.doc for row in self.db.view("form", "enabled", include_docs=True)]
        for form in forms:
            if form.get("ordinal") is None:
                form["ordinal"] = 0
        forms.sort(key=lambda i: i["ordinal"])
        if not self.current_user:
            self.render("home/anonymous.html", forms=forms)
        elif self.current_user["role"] == constants.ADMIN:
            self.home_admin(forms=forms)
        elif self.current_user["role"] == constants.STAFF:
            self.home_staff(forms=forms)
        else:
            self.home_user(forms=forms)

    def home_admin(self, **kwargs):
        "Home page for a current user having role 'admin'."
        view = self.db.view(
            "account", "status", key=constants.PENDING, include_docs=True
        )
        pending = [row.doc for row in view]
        pending.sort(key=lambda i: i["modified"], reverse=True)
        pending = pending[: settings["DISPLAY_MAX_PENDING_ACCOUNTS"]]
        view = self.db.view(
            "order",
            "status",
            descending=True,
            startkey=[constants.SUBMITTED, constants.CEILING],
            endkey=[constants.SUBMITTED],
            limit=settings["DISPLAY_MAX_RECENT_ORDERS"],
            reduce=False,
            include_docs=True,
        )
        orders = [row.doc for row in view]
        self.render("home/admin.html", pending=pending, orders=orders, **kwargs)

    def home_staff(self, **kwargs):
        "Home page for a current user having role 'staff'."
        view = self.db.view(
            "order",
            "status",
            descending=True,
            startkey=[constants.SUBMITTED, constants.CEILING],
            endkey=[constants.SUBMITTED],
            limit=settings["DISPLAY_MAX_RECENT_ORDERS"],
            reduce=False,
            include_docs=True,
        )
        orders = [row.doc for row in view]
        self.render("home/staff.html", orders=orders, **kwargs)

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
        orders = [row.doc for row in view]
        self.render("home/user.html", orders=orders, **kwargs)


class Status(RequestHandler):
    "Return JSON for the current status and some counts for the database."

    def get(self):
        result = dict(status="OK")
        result.update(orderportal.database.get_counts(self.db))
        self.write(result)


class Contact(RequestHandler):
    "Display contact information."

    def get(self):
        self.render("home/contact.html")


class About(RequestHandler):
    "Display 'About us' information."

    def get(self):
        self.render("home/about.html")


class Documentation(RequestHandler):
    "Documentation page."

    def get(self):
        self.render("home/documentation.html")


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
            ("Marko", marko.__version__, constants.MARKO_URL),
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
        self.render("home/software.html", software=software)


class Log(RequestHandler):
    "Singe log entry; JSON output."

    def get(self, iuid):
        log = self.get_entity(iuid, doctype=constants.LOG)
        log["iuid"] = log.pop("_id")
        log.pop("_rev")
        log.pop("orderportal_doctype")
        self.write(log)
        self.set_header("Content-Type", constants.JSON_MIMETYPE)


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
            self.see_other("home", error="Sorry, page not found.")


class SiteFile(RequestHandler):
    "Return a file configured for the site."

    def get(self, name):
        try:
            data = settings[f"SITE_{name.upper()}"]
            if data is None:
                raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(404)
        else:
            self.write(data["content"])
            self.set_header("Content-Type", data["content_type"])


class NoSuchEntity(RequestHandler):
    "Error message on home page."

    def get(self, path=None):
        self.logger.debug(f"Page not found: {path}")
        self.see_other("home", error="Sorry, page not found.")


class NoSuchEntityApiV1(RequestHandler):
    "Return Not Found status code."

    def get(self, path=None):
        self.logger.debug(f"Page not found: {path}")
        raise tornado.web.HTTPError(404)

    def post(self, path=None):
        self.logger.debug(f"Page not found: {path}")
        raise tornado.web.HTTPError(404)

    def put(self, path=None):
        self.logger.debug(f"Page not found: {path}")
        raise tornado.web.HTTPError(404)

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when API."
        pass
