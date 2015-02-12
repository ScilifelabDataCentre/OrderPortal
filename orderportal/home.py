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
            self.render('home_login.html')
        elif self.current_user['role'] == constants.ADMIN:
            self.dashboard_admin()
        elif self.current_user['role'] == constants.STAFF:
            self.dashboard_staff()
        else:
            self.dashboard_user()

    def dashboard_admin(self):
        view = self.db.view('user/pending', include_docs=True)
        pending = [self.get_presentable(r.doc) for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        self.render('home_admin.html', pending=pending)

    def dashboard_staff(self):
        self.render('home_staff.html')

    def dashboard_user(self):
        self.render('home_user.html')
