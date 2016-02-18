"OrderPortal: Home page variants, and a few general resources."

from __future__ import print_function, absolute_import

import logging

import couchdb
import markdown
import tornado
import tornado.web
import yaml

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class Home(RequestHandler):
    "Home page; dashboard. Contents according to role of logged-in account."

    def get(self):
        kwargs = dict(forms=[r.doc for r in
                             self.db.view('form/enabled', include_docs=True)],
                      news_items=self.get_news(),
                      events=self.get_events())
        if self.current_user and self.get_invitations(self.current_user['email']):
            url = self.reverse_url('account', self.current_user['email'])
            kwargs['message'] = u"""You have group invitations.
See your <a href="{0}">account</a>.""".format(url)
        if not self.current_user:
            self.render('home.html', **kwargs)
        elif self.current_user['role'] == constants.ADMIN:
            self.home_admin(**kwargs)
        elif self.current_user['role'] == constants.STAFF:
            self.home_staff(**kwargs)
        else:
            self.home_user(**kwargs)

    def home_admin(self, **kwargs):
        "Home page for a current user having role 'admin'."
        view = self.db.view('account/status',
                            key=constants.PENDING,
                            include_docs=True)
        pending = [r.doc for r in view]
        pending.sort(utils.cmp_modified, reverse=True)
        # XXX This status should not be hard-wired!
        view = self.db.view('order/status',
                            descending=True,
                            startkey=['submitted', constants.CEILING],
                            endkey=['submitted'],
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            reduce=False,
                            include_docs=True)
        orders = [r.doc for r in view]
        self.render('home_admin.html',
                    pending=pending,
                    orders=orders,
                    **kwargs)

    def home_staff(self, **kwargs):
        "Home page for a current user having role 'staff'."
        # XXX This status should not be hard-wired!
        view = self.db.view('order/status',
                            descending=True,
                            startkey=['accepted', constants.CEILING],
                            endkey=['accepted'],
                            limit=constants.MAX_STAFF_RECENT_ORDERS,
                            reduce=False,
                            include_docs=True)
        orders = [r.doc for r in view]
        self.render('home_staff.html',
                    orders=orders,
                    **kwargs)

    def home_user(self, **kwargs):
        "Home page for a current user having role 'user'."
        view = self.db.view('order/owner',
                            reduce=False,
                            include_docs=True,
                            descending=True,
                            startkey=[self.current_user['email'],
                                      constants.CEILING],
                            endkey=[self.current_user['email']],
                            limit=constants.MAX_ACCOUNT_RECENT_ORDERS)
        orders = [r.doc for r in view]
        self.render('home_user.html',
                    orders=orders,
                    **kwargs)


class Contact(RequestHandler):
    "Display contact information."

    def get(self):
        self.render('contact.html')


class TechInfo(RequestHandler):
    "Display information about the web site technology."

    def get(self):
        versions = dict(python=[('CouchDB-Python', couchdb.__version__),
                                ('tornado', tornado.version),
                                ('PyYAML', yaml.__version__),
                                ('markdown', markdown.version)],
                        other=[('<a href="http://couchdb.apache.org/">Apache CouchDB</a>',
                                utils.get_dbserver().version()),
                               ('<a href="http://getbootstrap.com/">bootstrap</a>', '3.3.4'),
                               ('<a href="https://jquery.com/">jQuery</a>', '1.11.13'),
                               ('<a href="https://github.com/GregDThomas/jquery-localtime">jQuery localtime</a>', '0.9.1'),
                               ('<a href="https://www.datatables.net/">jQuery DataTables</a>', '1.10.10')])
        self.render('techinfo.html',
                    version=orderportal.__version__,
                    versions=versions)


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
