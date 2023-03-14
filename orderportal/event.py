"Event list handling; meeting and seminar announcements for home page."

import tornado.web

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class EventSaver(saver.Saver):
    doctype = constants.EVENT


class Events(RequestHandler):
    "List of all events."

    def get(self):
        self.render("event/all.html", events=self.get_events())


class EventCreate(RequestHandler):
    "Create an event item."

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with EventSaver(handler=self) as saver:
            saver["date"] = self.get_argument("date")
            saver["title"] = self.get_argument("title")
            saver["text"] = self.get_argument("text", None) or ""
        self.see_other("home")


class EventEdit(RequestHandler):
    "Edit ot delete an event item."

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        self.check_admin()
        try:
            event = self.get_entity(iuid, constants.EVENT)
        except tornado.web.HTTPError:
            self.see_other("home", error="No such event.")
            return
        with EventSaver(doc=event, handler=self) as saver:
            saver["date"] = self.get_argument("date")
            saver["title"] = self.get_argument("title")
            saver["text"] = self.get_argument("text", None) or ""
            self.see_other("home")

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        event = self.get_entity(iuid, constants.EVENT)
        try:
            event = self.get_entity(iuid, constants.EVENT)
        except tornado.web.HTTPError:
            self.see_other("home", error="No such event.")
            return
        self.db.delete(event)
        self.see_other("home")
