"OrderPortal: News item handling."

from __future__ import print_function, absolute_import

import logging
import tornado.web

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class NewsSaver(saver.Saver):
    doctype = constants.NEWS


class News(RequestHandler):
    "Edit or delete a news item."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            raise tornado.web.HTTPError(404)
        with NewsSaver(doc=news, rqh=self) as saver:
            saver['text'] = self.get_argument('text')
        self.see_other('home')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            raise tornado.web.HTTPError(404)
        self.db.delete(news)
        self.see_other('home')


class NewsCreate(RequestHandler):
    "Create a news item."

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with NewsSaver(rqh=self) as saver:
            saver['text'] = self.get_argument('text')
        self.see_other('home')
