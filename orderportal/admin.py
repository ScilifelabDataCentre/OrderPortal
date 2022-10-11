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
        mod_settings["ACCOUNT_MESSAGES"] = f"<see file {mod_settings['ACCOUNT_MESSAGES_FILE']}>"
        mod_settings["COUNTRIES"] = f"<see file {mod_settings['COUNTRY_CODES_FILE']}>"
        mod_settings["COUNTRIES_LOOKUP"] = f"<computed from file {mod_settings['COUNTRY_CODES_FILE']}>"
        mod_settings["ORDER_MESSAGES"] = f"<see file {mod_settings['ORDER_MESSAGES_FILE']}>"
        mod_settings["ORDER_MESSAGES"] = f"<see file {mod_settings['ORDER_MESSAGES_FILE']}>"
        mod_settings["ORDER_STATUSES"] = f"<see file {mod_settings['ORDER_STATUSES_FILE']}>"
        mod_settings["ORDER_STATUSES_LOOKUP"] = f"<computed from file {mod_settings['ORDER_STATUSES_FILE']}>"
        mod_settings["ORDER_TRANSITIONS"] = f"<computed from file {mod_settings['ORDER_TRANSITIONS_FILE']}>"
        self.render("settings.html", settings=mod_settings)


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
