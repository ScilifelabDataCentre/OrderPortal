"OrderPortal: Events page."

from __future__ import unicode_literals, print_function, absolute_import

import logging
import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class EventSaver(saver.Saver):
    doctype = constants.EVENT


class Events(RequestHandler):
    "Page for viewing and handling all events items; creation, deletion."

    def get(self):
        self.render('events.html', events=self.get_events())

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with EventSaver(rqh=self) as saver:
            saver['date'] = self.get_argument('date')
            saver['title'] = self.get_argument('title')
            saver['text'] = self.get_argument('text', None)
        self.see_other('events')


class Event(RequestHandler):
    "Handle a events item."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        event = self.get_entity(iuid, constants.EVENT)
        if event is None:
            raise tornado.web.HTTPError(404)
        self.db.delete(event)
        self.see_other('events')
