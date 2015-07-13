"OrderPortal: Web application root."

from __future__ import print_function, absolute_import

import logging
import os
import sys

import couchdb
import markdown
import requests
import tornado
import tornado.web
import tornado.ioloop
import yaml

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import uimodules
from orderportal.requesthandler import RequestHandler

from orderportal.home import *
from orderportal.user import *
from orderportal.form import *
from orderportal.order import *
from orderportal.news import *
from orderportal.info import *
from orderportal.file import *
from orderportal.events import *


class Dummy(RequestHandler):
    def get(self, *args, **kwargs):
        self.redirect(self.reverse_url('home'))


def get_handlers():
    url = tornado.web.url
    return [url(r'/', Home, name='home'),
            url(r'/search', Dummy, name='search'),
            url(r'/orders', Orders, name='orders'),
            url(r'/order/([0-9a-f]{32})', Order, name='order'),
            url(r'/order/([0-9a-f]{32})/logs', OrderLogs, name='order_logs'),
            url(r'/order', OrderCreate, name='order_create'),
            url(r'/order/([0-9a-f]{32})/edit', OrderEdit, name='order_edit'),
            url(r'/order/([0-9a-f]{32})/transition/(\w+)',
                OrderTransition, name='order_transition'),
            url(r'/orders/([^/]+)', OrdersUser, name='orders_user'),
            # url(r'/order/([0-9a-f]{32})/copy', OrderCopy, name='order_copy'),
            url(r'/users', Users, name='users'),
            url(r'/user/([^/]+)', User, name='user'),
            url(r'/user/([^/]+)/logs', UserLogs, name='user_logs'),
            url(r'/user/([^/]+)/edit', UserEdit, name='user_edit'),
            url(r'/login', Login, name='login'),
            url(r'/logout', Logout, name='logout'),
            url(r'/reset', Reset, name='reset'),
            url(r'/password', Password, name='password'),
            url(r'/register', Register, name='register'),
            url(r'/user/([^/]+)/enable', UserEnable, name='user_enable'),
            url(r'/user/([^/]+)/disable', UserDisable, name='user_disable'),
            url(r'/forms', Forms, name='forms'),
            url(r'/form/([0-9a-f]{32})', Form, name='form'),
            url(r'/form/([0-9a-f]{32})/logs', FormLogs, name='form_logs'),
            url(r'/form', FormCreate, name='form_create'),
            url(r'/form/([0-9a-f]{32})/edit', FormEdit, name='form_edit'),
            url(r'/form/([0-9a-f]{32})/copy', FormCopy, name='form_copy'),
            url(r'/form/([0-9a-f]{32})/enable', FormEnable, name='form_enable'),
            url(r'/form/([0-9a-f]{32})/disable',
                FormDisable, name='form_disable'),
            url(r'/form/([0-9a-f]{32})/field',
                FormFieldCreate, name='field_create'),
            url(r'/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)',
                FormFieldEdit, name='field_edit'),
            url(r'/news', News, name='news'),
            url(r'/new/([0-9a-f]{32})', New, name='new'),
            url(r'/events', Events, name='events'),
            url(r'/event/([0-9a-f]{32})', Event, name='event'),
            url(r'/infos', Infos, name='infos'),
            url(r'/info', InfoCreate, name='info_create'),
            url(r'/info/([^/]+)', Info, name='info'),
            url(r'/info/([^/]+)/edit', InfoEdit, name='info_edit'),
            url(r'/info/([^/]+)/logs', InfoLogs, name='info_logs'),
            url(r'/files', Files, name='files'),
            url(r'/file', FileCreate, name='file_create'),
            url(r'/file/([^/]+)', File, name='file'),
            url(r'/file/([^/]+)/download', FileDownload, name='file_download'),
            url(r'/file/([^/]+)/meta', FileMeta, name='file_meta'),
            url(r'/file/([^/]+)/edit', FileEdit, name='file_edit'),
            url(r'/file/([^/]+)/logs', FileLogs, name='file_logs'),
            url(r'/text/([^/]+)', Text, name='text'),
            url(r'/log/([0-9a-f]{32})', Log, name='log'),
            url(r'/([0-9a-f]{32})', Entity, name='entity'),
            ]

def main():
    logging.info("tornado debug: %s, logging debug: %s",
                 settings['TORNADO_DEBUG'], settings['LOGGING_DEBUG'])
    logging.debug("OrderPortal version %s", orderportal.__version__)
    logging.debug("CouchDB version %s", utils.get_dbserver().version())
    logging.debug("CouchDB-Python version %s", couchdb.__version__)
    logging.debug("tornado version %s", tornado.version)
    logging.debug("PyYAML version %s", yaml.__version__)
    logging.debug("requests version %s", requests.__version__)
    logging.debug("Markdown version %s", markdown.version)
    application = tornado.web.Application(
        handlers=get_handlers(),
        debug=settings.get('TORNADO_DEBUG', False),
        cookie_secret=settings['COOKIE_SECRET'],
        ui_modules=uimodules,
        template_path=settings.get('TEMPLATE_PATH', 'html'),
        static_path=settings.get('STATIC_PATH', 'static'),
        login_url=r'/home')
    application.listen(settings['PORT'], xheaders=True)
    logging.info("OrderPortal %s web server PID %s on port %s",
                 settings['DATABASE'], os.getpid(), settings['PORT'])
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    parser = utils.get_command_line_parser(description='Web app server.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    main()
