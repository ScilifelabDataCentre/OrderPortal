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


class GlobalModes(RequestHandler):
    "Page for display and change of global modes."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('global_modes.html')

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


class Settings(RequestHandler):
    "Page displaying settings info."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        mod_settings = settings.copy()
        # Don't show the password in the CouchDB URL
        url = settings['DB_SERVER']
        match = re.search(r':([^/].+)@', url)
        if match:
            url = list(url)
            url[match.start(1):match.end(1)] = '***'
            mod_settings['DB_SERVER'] = ''.join(url)
        params = ['ROOT_DIR', 'SETTINGS_FILEPATH',
                  'BASE_URL', 'SITE_NAME', 'SITE_SUPPORT_EMAIL',
                  'DB_SERVER', 'DATABASE',
                  'TORNADO_DEBUG', 'LOGGING_DEBUG',
                  'LOGIN_MAX_AGE_DAYS', 'LOGIN_MAX_FAILURES',
                  'SITE_DIR', 'ACCOUNT_MESSAGES_FILEPATH',
                  'ORDER_STATUSES_FILEPATH', 'ORDER_TRANSITIONS_FILEPATH',
                  'ORDER_MESSAGES_FILEPATH', 'UNIVERSITIES_FILEPATH',
                  'COUNTRY_CODES_FILEPATH', 'SUBJECT_TERMS_FILEPATH']
        self.render('settings.html', params=params, settings=mod_settings)


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


class OrderStatuses(RequestHandler):
    "Page displaying currently defined order statuses and transitions."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('order_statuses.html')


class AdminOrderMessages(RequestHandler):
    "Page for displaying order messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('admin_order_messages.html')


class AdminAccountMessages(RequestHandler):
    "Page for displaying account messages configuration."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('admin_account_messages.html')


class Statistics(RequestHandler):
    "Display statistics for the database."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('order/status', reduce=True)
        try:
            r = list(view)[0]
        except IndexError:
            orders = dict(count=0)
        else:
            orders = dict(count=r.value)
        view = self.db.view('order/status',
                            group_level=1,
                            startkey=[''],
                            endkey=[constants.CEILING])
        orders['status'] = dict([(r.key[0], r.value) for r in view])
        self.render('statistics.html', orders=orders)
