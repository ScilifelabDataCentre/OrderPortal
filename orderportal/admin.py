"Admin pages."

from __future__ import print_function, absolute_import

import logging
import re

import tornado.web

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
        origin = self.get_argument('origin', self.absolute_reverse_url('texts'))
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
        url = self.get_argument('origin', self.absolute_reverse_url('texts'))
        self.redirect(url, status=303)


class Texts(RequestHandler):
    "Page listing texts used in the web site."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('texts.html', texts=sorted(constants.TEXTS.items()))


class Statuses(RequestHandler):
    "Page displaying currently defined statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('statuses.html')


class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        # Don't show the password
        url = settings['DB_SERVER']
        match = re.search(r':([^/].+)@', url)
        if match:
            url = list(url)
            url[match.start(1):match.end(1)] = '***'
            url = ''.join(url)
        params = [('Settings', settings['SETTINGS_FILEPATH']),
                  ('Database server', url),
                  ('Database', settings['DATABASE']),
                  ('Site name', settings['SITE_NAME']),
                  ('Site directory', settings['SITE_DIR']),
                  ('Tornado debug', settings['TORNADO_DEBUG']),
                  ('logging debug', settings['LOGGING_DEBUG']),
                  ('account messages', settings['ACCOUNT_MESSAGES_FILEPATH']),
                  ('order statuses', settings['ORDER_STATUSES_FILEPATH']),
                  ('order transitions', settings['ORDER_TRANSITIONS_FILEPATH']),
                  ('universities', settings.get('UNIVERSITIES_FILEPATH')),
                  ('country codes', settings.get('COUNTRY_CODES_FILEPATH')),
                  ('subject terms', settings.get('SUBJECT_TERMS_FILEPATH')),
                  ]
        self.render('settings.html', params=params)


class GlobalModes(RequestHandler):
    "Page for display and change of global modes."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('global_modes.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        try:
            mode = self.get_argument('mode')
            if mode not in self.global_modes: raise ValueError
            self.global_modes[mode] = utils.to_bool(self.get_argument('value'))
        except (tornado.web.MissingArgumentError, ValueError, TypeError):
            pass
        else:
            # Create global_modes meta document if it does not exist.
            if '_id' not in self.global_modes:
                self.global_modes['_id'] = 'global_modes'
                self.global_modes[constants.DOCTYPE] = constants.META
            self.db.save(self.global_modes)
        self.see_other('global_modes')
