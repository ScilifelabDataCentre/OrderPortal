"OrderPortal: Admin pages."

from __future__ import print_function, absolute_import

import logging

import couchdb
import markdown
import tornado
import yaml

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class TextSaver(saver.Saver):
    doctype = constants.TEXT


class Text(RequestHandler):
    "Edit page for information text."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        try:
            text = self.get_entity_view('text/name', name)
        except tornado.web.HTTPError:
            text = dict(name=name)
        origin = self.get_argument('origin', self.absolute_reverse_url('home'))
        self.render('text.html', text=text, origin=origin)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        try:
            text = self.get_entity_view('text/name', name)
        except tornado.web.HTTPError:
            text = dict(name=name)
        with TextSaver(doc=text, rqh=self) as saver:
            saver['text'] = self.get_argument('text')
        url = self.get_argument('origin', self.absolute_reverse_url('home'))
        self.redirect(url, status=303)


class Statuses(RequestHandler):
    "Page displaying currently defined statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('statuses.html')


class Config(RequestHandler):
    "Page displaying configuration info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        params = [('OrderPortal', orderportal.__version__),
                  ('Database', settings['DATABASE']),
                  ('CouchDB', utils.get_dbserver().version()),
                  ('CouchDB-Python', couchdb.__version__),
                  ('tornado', tornado.version),
                  ('PyYAML', yaml.__version__),
                  ('markdown', markdown.version)]
        params.append(('Site name', settings['SITE_NAME']))
        params.append(('Site directory', settings['SITE_DIR']))
        params.append(('Tornado debug', settings['TORNADO_DEBUG']))
        params.append(('logging debug', settings['LOGGING_DEBUG']))
        params.append(('account messages',
                       settings['ACCOUNT_MESSAGES_FILENAME']))
        params.append(('order statuses', settings['ORDER_STATUSES_FILENAME']))
        params.append(('order transitions',
                       settings['ORDER_TRANSITIONS_FILENAME']))
        params.append(('universities', settings['UNIVERSITIES_FILENAME']))

        self.render('config.html', params=params)
