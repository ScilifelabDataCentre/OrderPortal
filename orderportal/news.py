"News item handling; news announcements for home page."

import logging
import tornado.web

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class NewsSaver(saver.Saver):
    doctype = constants.NEWS


class NewsEdit(RequestHandler):
    "Edit or delete a news item."

    @tornado.web.authenticated
    def post(self, iuid):
        if self.readonly(): return
        self.check_admin()
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            self.see_other("home", error="No such news item.")
            return
        with NewsSaver(doc=news, rqh=self) as saver:
            saver["date"] = self.get_argument("date", "") or utils.today()
            saver["title"] = self.get_argument("title")
            saver["text"] = self.get_argument("text", "")
        self.see_other("home")

    @tornado.web.authenticated
    def delete(self, iuid):
        if self.readonly(): return
        self.check_admin()
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            self.see_other("home", error="No such news item.")
            return
        self.db.delete(news)
        self.see_other("home")


class NewsCreate(RequestHandler):
    "Create a news item."

    @tornado.web.authenticated
    def post(self):
        if self.readonly(): return
        self.check_admin()
        with NewsSaver(rqh=self) as saver:
            saver["date"] = utils.today()
            saver["title"] = self.get_argument("title")
            saver["text"] = self.get_argument("text", "")
        self.see_other("home")


class News(RequestHandler):
    "List all news items."

    def get(self):
        self.render("news.html", news_items=self.get_news())
