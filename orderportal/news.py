"News item handling; news announcements for home page."

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
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            self.see_other('home', error='No such news item.')
            return
        with NewsSaver(doc=news, rqh=self) as saver:
            saver['date'] = self.get_argument('date', None)
            saver['title'] = self.get_argument('title')
            saver['text'] = self.get_argument('text', None) or ''
        self.see_other('home')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        news = self.get_entity(iuid, constants.NEWS)
        if news is None:
            self.see_other('home', error='No such news item.')
            return
        self.db.delete(news)
        self.see_other('home')


class NewsCreate(RequestHandler):
    "Create a news item."

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with NewsSaver(rqh=self) as saver:
            saver['date'] = self.get_argument('date', None)
            saver['title'] = self.get_argument('title')
            saver['text'] = self.get_argument('text', None) or ''
        self.see_other('home')
