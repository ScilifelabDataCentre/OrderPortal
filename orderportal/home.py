"Home page variants, and a few general resources."



import logging
import sys
from collections import OrderedDict as OD

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
        forms = [r.doc for r in self.db.view('form/enabled', include_docs=True)]
        for f in forms:
            if f.get('ordinal') is None: f['ordinal'] = 0
        forms.sort(key=lambda i: i['ordinal'])
        kwargs = dict(
            forms=forms,
            news_items=self.get_news(limit=settings['DISPLAY_MAX_NEWS']),
            events=self.get_events(upcoming=True))
        if self.current_user and self.get_invitations(self.current_user['email']):
            url = self.reverse_url('account', self.current_user['email'])
            kwargs['message'] = """You have group invitations.
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
        pending.sort(key=lambda i: i['modified'], reverse=True)
        pending = pending[:settings['DISPLAY_MAX_PENDING_ACCOUNTS']]
        # XXX This status should not be hard-wired!
        view = self.db.view('order/status',
                            descending=True,
                            startkey=['submitted', constants.CEILING],
                            endkey=['submitted'],
                            limit=settings['DISPLAY_MAX_RECENT_ORDERS'],
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
                            limit=settings['DISPLAY_MAX_RECENT_ORDERS'],
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
                            limit=settings['DISPLAY_MAX_RECENT_ORDERS'])
        orders = [r.doc for r in view]
        self.render('home_user.html',
                    orders=orders,
                    **kwargs)


class Contact(RequestHandler):
    "Display contact information."

    def get(self):
        self.render('contact.html')


class About(RequestHandler):
    "Display 'About us' information."

    def get(self):
        self.render('about.html')


class Software(RequestHandler):
    "Display software information for the web site."

    def get(self):
        info = [
            ('Python', 'https://www.python.org',
             "%s.%s.%s" % sys.version_info[0:3], 'installed'),
            ('CouchDB server', 'http://couchdb.apache.org/',
             utils.get_dbserver().version(), 'installed'),
            ('CouchDB-Python', 'https://pypi.org/project/CouchDB/',
             couchdb.__version__, 'installed'),
            ('tornado', 'https://pypi.org/project/tornado/',
             tornado.version, 'installed'),
            ('PyYAML', 'https://pypi.org/project/PyYAML/',
             yaml.__version__, 'installed'),
            ('markdown', 'https://pypi.org/project/Markdown/',
             markdown.version, 'installed'),
            ('bootstrap', 'https://getbootstrap.com/docs/3.3/', 
             '3.3.7', 'CDN'),
            ('jQuery', 'https://jquery.com/', '1.12.4', 'CDN'),
            ('jQuery-UI', 'https://jqueryui.com/', '1.11.4', 'CDN'),
            ('jQuery localtime', 
             'https://github.com/GregDThomas/jquery-localtime',
             '0.9.1', 'in distro'),
            ('jQuery DataTables', 'https://www.datatables.net/',
             '1.10.11', 'CDN')
            ]
        self.render('software.html',
                    version=orderportal.__version__,
                    info=info)


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
            self.redirect(self.order_reverse_url(doc))
        elif doc[constants.DOCTYPE] == constants.FORM:
            self.see_other('form', doc['_id'])
        elif doc[constants.DOCTYPE] == constants.ACCOUNT:
            self.see_other('account', doc['email'])
        else:
            self.see_other('home', error='Sorry, no such entity found.')


class NoSuchEntity(RequestHandler):
    "Error message on home page."

    def get(self, path=None):
        logging.debug("No such entity: %s", path)
        self.see_other('home', error='Sorry, no such entity found.')


class NoSuchEntityApiV1(RequestHandler):
    "Return Not Found status code."

    def get(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def post(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def put(self, path=None):
        logging.debug("No such entity: %s", path)
        raise tornado.web.HTTPError(404)

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when API."
        pass


class Status(RequestHandler):
    "Return JSON for the current status and some counts for the database."

    def get(self):
        try:
            n_orders = list(self.db.view("order/status", reduce=True))[0].value
        except IndexError:
            n_orders = 0
        try:
            n_forms = list(self.db.view("form/all", reduce=True))[0].value
        except IndexError:
            n_forms = 0
        try:
            n_accounts = list(self.db.view("account/all", reduce=True))[0].value
        except IndexError:
            n_accounts = 0
        self.write(dict(status="OK",
                        n_orders=n_orders,
                        n_forms=n_forms,
                        n_accounts=n_accounts))
