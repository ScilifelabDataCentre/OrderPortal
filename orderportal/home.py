"OrderPortal: Home page."

from __future__ import unicode_literals, print_function, absolute_import

import logging
import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler
from orderportal.saver import Saver


class NewsMixin(object):
    "Mixin for news items handling."

    def get_news(self):
        return []


class EventsMixin(object):
    "Mixin for events items handling."

    def get_events(self):
        return []


class Home(NewsMixin, EventsMixin, RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in user."

    def get(self):
        if not self.current_user:
            self.render('home.html',
                        news=self.get_news(),
                        events=self.get_events())
        elif self.current_user['role'] == constants.ADMIN:
            self.home_admin(news=self.get_news(),
                            events=self.get_events())
        elif self.current_user['role'] == constants.STAFF:
            self.home_staff(news=self.get_news(),
                            events=self.get_events())
        else:
            self.home_user(news=self.get_news(),
                            events=self.get_events())

    def home_admin(self, news, events):
        view = self.db.view('user/pending', include_docs=True)
        pending = [self.get_presentable(r.doc) for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        self.render('home_admin.html', pending=pending,
                    news=news, events=events)

    def home_staff(self, news, events):
        self.render('home_staff.html', news=news, events=events)

    def home_user(self, news, events):
        forms = [self.get_presentable(r.doc) for r in
                 self.db.view('form/enabled', include_docs=True)]
        view = self.db.view('order/owner', descending=True,
                            limit=10, include_docs=True,
                            key=self.current_user['email'])
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('home_user.html', forms=forms, orders=orders,
                    news=news, events=events)


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


class About(RequestHandler):
    "Page describing the site."

    def get(self):
        self.render('about.html')


class News(NewsMixin, RequestHandler):
    "Edit page for news items."

    @tornado.web.authenticated
    def get(self):
        self.render('news.html', news=self.get_news())


class Events(EventsMixin, RequestHandler):
    "Edit page for events items."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('events.html', events=self.get_events())


class TextSaver(Saver):
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
        origin = self.get_argument('origin', self.reverse_url('home'))
        self.render('text.html', text=text, origin=origin)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        try:
            text = self.get_entity_view('text/name', name)
        except tornado.web.HTTPError:
            text = dict(name=name)
        with TextSaver(doc=text, rqh=self) as saver:
            saver['markdown'] = self.get_argument('markdown')
        url = self.get_argument('origin', self.absolute_reverse_url('home'))
        self.redirect(url, status=303)
