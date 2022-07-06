"Admin pages."

import logging
import re

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class GlobalModes(RequestHandler):
    "Page for display and change of global modes."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("global_modes.html")

    def post(self):
        self.check_admin()
        try:
            mode = self.get_argument("mode")
            if mode not in self.global_modes:
                raise ValueError
            self.global_modes[mode] = utils.to_bool(self.get_argument("value"))
        except (tornado.web.MissingArgumentError, ValueError, TypeError):
            pass
        else:
            # Create global_modes meta document if it does not exist.
            if "_id" not in self.global_modes:
                self.global_modes["_id"] = "global_modes"
                self.global_modes[constants.DOCTYPE] = constants.META
            self.db.put(self.global_modes)
        self.see_other("global_modes")


class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        mod_settings = settings.copy()
        # Add the root dir
        mod_settings["ROOT"] = constants.ROOT
        # Do not show the email password
        if mod_settings["EMAIL"].get("PASSWORD"):
            mod_settings["EMAIL"]["PASSWORD"] = "*** hidden ***"
        # Don't show the password in the CouchDB URL
        url = settings["DATABASE_SERVER"]
        match = re.search(r":([^/].+)@", url)
        if match:
            url = list(url)
            url[match.start(1) : match.end(1)] = "password"
            mod_settings["DATABASE_SERVER"] = "".join(url)
        params = [
            "ROOT",
            "SITE_DIR",
            "SETTINGS_FILE",
            "BASE_URL",
            "BASE_URL_PATH_PREFIX",
            "PORT",
            "SITE_NAME",
            "SITE_SUPPORT_EMAIL",
            "DATABASE_SERVER",
            "DATABASE_NAME",
            "DATABASE_ACCOUNT",
            "TORNADO_DEBUG",
            "LOGGING_FILEPATH",
            "LOGGING_DEBUG",
            "LOGGING_FILEPATH",
            "EMAIL",
            "MESSAGE_SENDER_EMAIL",
            "LOGIN_MAX_AGE_DAYS",
            "LOGIN_MAX_FAILURES",
            "ORDER_STATUSES_FILE",
            "ORDER_TRANSITIONS_FILE",
            "ORDER_MESSAGES_FILE",
            "ORDER_USER_TAGS",
            "ORDERS_SEARCH_FIELDS",
            "ORDERS_LIST_FIELDS",
            "ORDERS_LIST_STATUSES",
            "ORDER_AUTOPOPULATE",
            "ORDER_TAGS",
            "UNIVERSITIES_FILE",
            "COUNTRY_CODES_FILE",
            "SUBJECT_TERMS_FILE",
            "ACCOUNT_MESSAGES_FILE",
            "ACCOUNT_PI_INFO",
            "ACCOUNT_POSTAL_INFO",
            "ACCOUNT_INVOICE_INFO",
            "ACCOUNT_FUNDER_INFO",
            "ACCOUNT_FUNDER_INFO_GENDER",
            "ACCOUNT_FUNDER_INFO_GROUP_SIZE",
            "ACCOUNT_FUNDER_INFO_SUBJECT",
            "ACCOUNT_DEFAULT_COUNTRY_CODE",
        ]
        self.render("settings.html", params=params, settings=mod_settings)


class TextSaver(saver.Saver):
    doctype = constants.TEXT


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
