"OrderPortal: Home page variants, and a few general resources."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in account."

    def get(self):
        if not self.current_user:
            self.render('home.html',
                        news_items=self.get_news(),
                        events=self.get_events(),
                        message=self.get_invited_message())
        elif self.current_user['role'] == constants.ADMIN:
            self.home_admin(news_items=self.get_news(),
                            events=self.get_events(),
                            message=self.get_invited_message())
        elif self.current_user['role'] == constants.STAFF:
            self.home_staff(news_items=self.get_news(),
                            events=self.get_events(),
                            message=self.get_invited_message())
        else:
            self.home_user(news_items=self.get_news(),
                           events=self.get_events(),
                           message=self.get_invited_message())

    def get_invited_message(self):
        if self.get_invitations():
            return 'You have group invitations. See the page for your account.'
        else:
            return None

    def home_admin(self, **kwargs):
        "Home page for a current user having role 'admin'."
        view = self.db.view('account/status',
                            key=constants.PENDING,
                            include_docs=True)
        pending = [r.doc for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        # XXX This status is not hard-wired, so this may yield nothing.
        view = self.db.view('order/status',
                            startkey=['submitted', constants.HIGH_CHAR],
                            endkey=['submitted'],
                            descending=True,
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            include_docs=True)
        orders = [r.doc for r in view]
        self.render('home_admin.html',
                    pending=pending,
                    orders=orders,
                    **kwargs)

    def home_staff(self, **kwargs):
        "Home page for a current user having role 'staff'."
        # XXX This status is not hard-wired, so this may yield nothing.
        view = self.db.view('order/status',
                            startkey=['accepted', constants.HIGH_CHAR],
                            endkey=['accepted'],
                            descending=True,
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            include_docs=True)
        orders = [r.doc for r in view]
        self.render('home_staff.html',
                    orders=orders,
                    **kwargs)

    def home_user(self, **kwargs):
        "Home page for a current user having role 'user'."
        forms = [r.doc for r in self.db.view('form/enabled', include_docs=True)]
        view = self.db.view('order/owner',
                            descending=True,
                            limit=constants.MAX_ACCOUNT_RECENT_ORDERS,
                            include_docs=True,
                            key=self.current_user['email'])
        orders = [r.doc for r in view]
        self.render('home_user.html',
                    forms=forms,
                    orders=orders,
                    **kwargs)


class Log(RequestHandler):
    "Singe log entry; JSON output."

    def get(self, iuid):
        log = self.get_entity(iuid, doctype=constants.LOG)
        log['iuid'] = log.pop('_id')
        log.pop('_rev')
        log.pop('orderportal_doctype')
        self.write(log)
        self.set_header('Content-Type', constants.JSON_MIME)


class Entity(RequestHandler):
    "Redirect to the entity given by the IUID, if any."

    def get(self, iuid):
        "Login and privileges are checked by the entity redirected to."
        doc = self.get_entity(iuid)
        if doc[constants.DOCTYPE] == constants.ORDER:
            self.see_other('order', doc['_id'])
        elif doc[constants.DOCTYPE] == constants.FORM:
            self.see_other('form', doc['_id'])
        elif doc[constants.DOCTYPE] == constants.ACCOUNT:
            self.see_other('account', doc['email'])
        else:
            raise tornado.web.HTTPError(404)
