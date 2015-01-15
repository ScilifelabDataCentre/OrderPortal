"OrderPortal: Web application root."

from __future__ import unicode_literals, print_function, absolute_import

import os
import sys
import logging

import tornado
import tornado.web
import tornado.ioloop
import couchdb
import yaml

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import uimodules
from orderportal.requesthandler import RequestHandler

# from orderportal.order import *
# from orderportal.user import *


class Home(RequestHandler):
    "Home page."

    def get(self):
        self.render('home.html')


URL = tornado.web.url

handlers = \
    [URL(r'/', Home, name='home'),
     # URL(r'/orders', Orders, name='orders'),
     # URL(r'/order/([0-9a-f]{32})', Order, name='order'),
     # URL(r'/field/([0-9a-f]{32})', Field, name='field'),
     # URL(r'/order/([0-9a-f]{32})/edit', OrderEdit, name='order_edit'),
     # URL(r'/order/([0-9a-f]{32})/copy', OrderCopy, name='order_copy'),
     # URL(r'/order/([0-9a-f]{32})/log', OrderLog, name='order_log'),
     # URL(r'/users', Users, name='users'),
     # URL(r'/user/([^/]+)', User, name='user'),
     # URL(r'/user/([^/]+)/edit', UserEdit, name='user_edit'),
     # URL(r'/user', UserRegister, name='user_register'),
     # URL(r'/user/([^/]+)/block', UserBlock, name='user_block'),
     # URL(r'/user/([^/]+)/activate', UserActivate, name='user_activate'),
     # URL(r'/user/([0-9a-f]{32})/log', UserLog, name='user_log'),
     # URL(r'/login', Login, name='login'),
     # URL(r'/login/code', LoginCode, name='login_code'),
     # URL(r'/logout', Logout, name='logout'),
     ]


def main(filepath=None):
    utils.load_settings(filepath=filepath)
    logging.info("tornado debug: %s, logging debug: %s",
                 settings['TORNADO_DEBUG'], settings['LOGGING_DEBUG'])
    logging.debug("orderportal %s, tornado %s, couchdb module %s, pyyaml %s",
                  orderportal.__version__,
                  tornado.version,
                  couchdb.__version__,
                  yaml.__version__)
    application = tornado.web.Application(
        handlers=handlers,
        debug=settings.get('TORNADO_DEBUG', False),
        cookie_secret=settings['COOKIE_SECRET'],
        ui_modules=uimodules,
        template_path=settings.get('TEMPLATE_PATH', 'html'),
        static_path=settings.get('STATIC_PATH', 'static'),
        login_url=r'/login')
    application.listen(settings['PORT'], xheaders=True)
    logging.info("orderportal web server PID %s on port %s",
                 os.getpid(), settings['PORT'])
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    try:
        filepath = sys.argv[1]
    except IndexError:
        filepath = None
    main(filepath)
