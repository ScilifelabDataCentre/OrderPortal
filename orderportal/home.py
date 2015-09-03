"OrderPortal: Home page variants, and a few general resources."

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


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in user."

    def get(self):
        if not self.current_user:
            self.render('home.html',
                        news_items=self.get_news(),
                        events=self.get_events())
        elif self.current_user['role'] == constants.ADMIN:
            self.home_admin(news_items=self.get_news(),
                            events=self.get_events())
        elif self.current_user['role'] == constants.STAFF:
            self.home_staff(news_items=self.get_news(),
                            events=self.get_events())
        else:
            self.home_user(news_items=self.get_news(),
                           events=self.get_events())

    def home_admin(self, news_items, events):
        view = self.db.view('user/status',
                            key=constants.PENDING,
                            include_docs=True)
        pending = [self.get_presentable(r.doc) for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        view = self.db.view('order/modified',
                            descending=True,
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            include_docs=True)
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('home_admin.html', pending=pending, orders=orders,
                    news_items=news_items, events=events)

    def home_staff(self, news_items, events):
        view = self.db.view('order/modified',
                            descending=True,
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            include_docs=True)
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('home_staff.html', orders=orders,
                    news_items=news_items, events=events)

    def home_user(self, news_items, events):
        forms = [self.get_presentable(r.doc) for r in
                 self.db.view('form/enabled', include_docs=True)]
        view = self.db.view('order/owner',
                            descending=True,
                            limit=constants.MAX_USER_RECENT_ORDERS,
                            include_docs=True,
                            key=self.current_user['email'])
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('home_user.html', forms=forms, orders=orders,
                    news_items=news_items, events=events)


class Log(RequestHandler):
    "Singe log entry; JSON output."

    def get(self, iuid):
        doc = self.get_entity(iuid, doctype=constants.LOG)
        self.write(self.get_presentable(doc))
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
        elif doc[constants.DOCTYPE] == constants.USER:
            self.see_other('user', doc['email'])
        else:
            raise tornado.web.HTTPError(404)


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


class Tech(RequestHandler):
    "Page displaying some technical information."

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
        self.render('tech.html', params=params)
