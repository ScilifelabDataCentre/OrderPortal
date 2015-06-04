"OrderPortal: Home page."

from __future__ import unicode_literals, print_function, absolute_import

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in user."

    def get(self):
        if not self.current_user:
            self.render('home.html')
        elif self.current_user['role'] == constants.ADMIN:
            self.home_admin()
        elif self.current_user['role'] == constants.STAFF:
            self.home_staff()
        else:
            self.home_user()

    def home_admin(self):
        view = self.db.view('user/pending', include_docs=True)
        pending = [self.get_presentable(r.doc) for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        self.render('home_admin.html', pending=pending)

    def home_staff(self):
        self.render('home_staff.html')

    def home_user(self):
        forms = [self.get_presentable(r.doc) for r in
                 self.db.view('form/enabled', include_docs=True)]
        view = self.db.view('order/owner', descending=True,
                            limit=10, include_docs=True,
                            key=self.current_user['email'])
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('home_user.html', forms=forms, orders=orders)


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
            url = self.absolute_reverse_url('order', doc['_id'])
        elif doc[constants.DOCTYPE] == constants.FORM:
            url = self.absolute_reverse_url('form', doc['_id'])
        elif doc[constants.DOCTYPE] == constants.USER:
            url = self.absolute_reverse_url('user', doc['email'])
        else:
            raise tornado.web.HTTPError(404)
        self.see_other(url)
