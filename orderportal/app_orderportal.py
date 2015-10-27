"OrderPortal: Web application root."

from __future__ import print_function, absolute_import

import logging
import os

import tornado.web
import tornado.ioloop

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import uimodules
from orderportal.requesthandler import RequestHandler

from orderportal.home import *
from orderportal.admin import *
from orderportal.account import *
from orderportal.group import *
from orderportal.form import *
from orderportal.order import *
from orderportal.news import *
from orderportal.info import *
from orderportal.file import *
from orderportal.event import *
from orderportal.search import *


class Dummy(RequestHandler):
    def get(self, *args, **kwargs):
        self.redirect(self.reverse_url('home'))


def get_handlers():
    url = tornado.web.url
    return [url(r'/', Home, name='home'),
            url(r'/order/([0-9a-f]{32})', Order, name='order'),
            url(r'/order/([0-9a-f]{32})/logs', OrderLogs, name='order_logs'),
            url(r'/order', OrderCreate, name='order_create'),
            url(r'/order/([0-9a-f]{32})/edit', OrderEdit, name='order_edit'),
            url(r'/order/([0-9a-f]{32})/transition/(\w+)',
                OrderTransition, name='order_transition'),
            url(r'/order/([0-9a-f]{32})/clone', OrderClone, name='order_clone'),
            url(r'/order/([0-9a-f]{32})/file',
                OrderAttach, name='order_attach'),
            url(r'/order/([0-9a-f]{32})/file/([^/]+)',
                OrderFile, name='order_file'),
            url(r'/orders', Orders, name='orders'),
            url(r'/accounts', Accounts, name='accounts'),
            url(r'/account', AccountCurrent, name='account_current'),
            url(r'/account/([^/]+)', Account, name='account'),
            url(r'/account/([^/]+)/orders',
                AccountOrders, name='account_orders'),
            url(r'/account/([^/]+)/groups/orders',
                AccountGroupsOrders, name='account_groups_orders'),
            url(r'/account/([^/]+)/logs', AccountLogs, name='account_logs'),
            url(r'/account/([^/]+)/messages',
                AccountMessages, name='account_messages'),
            url(r'/account/([^/]+)/edit', AccountEdit, name='account_edit'),
            url(r'/group', GroupCreate, name='group_create'),
            url(r'/group/([0-9a-f]{32})', Group, name='group'),
            url(r'/group/([0-9a-f]{32})/edit', GroupEdit, name='group_edit'),
            url(r'/group/([0-9a-f]{32})/accept',
                GroupAccept, name='group_accept'),
            url(r'/group/([0-9a-f]{32})/decline',
                GroupDecline, name='group_decline'),
            url(r'/group/([0-9a-f]{32})/logs', GroupLogs, name='group_logs'),
            url(r'/groups', Groups, name='groups'),
            url(r'/search', Search, name='search'),
            url(r'/login', Login, name='login'),
            url(r'/logout', Logout, name='logout'),
            url(r'/reset', Reset, name='reset'),
            url(r'/password', Password, name='password'),
            url(r'/register', Register, name='register'),
            url(r'/account/([^/]+)/enable',
                AccountEnable, name='account_enable'),
            url(r'/account/([^/]+)/disable',
                AccountDisable, name='account_disable'),
            url(r'/forms', Forms, name='forms'),
            url(r'/form/([0-9a-f]{32})', Form, name='form'),
            url(r'/form/([0-9a-f]{32})/logs', FormLogs, name='form_logs'),
            url(r'/form', FormCreate, name='form_create'),
            url(r'/form/([0-9a-f]{32})/edit', FormEdit, name='form_edit'),
            url(r'/form/([0-9a-f]{32})/clone', FormClone, name='form_clone'),
            url(r'/form/([0-9a-f]{32})/pending',
                FormPending, name='form_pending'),
            url(r'/form/([0-9a-f]{32})/testing',
                FormTesting, name='form_testing'),
            url(r'/form/([0-9a-f]{32})/enable', FormEnable, name='form_enable'),
            url(r'/form/([0-9a-f]{32})/disable',
                FormDisable, name='form_disable'),
            url(r'/form/([0-9a-f]{32})/field',
                FormFieldCreate, name='field_create'),
            url(r'/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)',
                FormFieldEdit, name='field_edit'),
            url(r'/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)/descr',
                FormFieldEditDescr, name='field_edit_descr'),
            url(r'/form/([0-9a-f]{32})/orders',
                FormOrders, name='form_orders'),
            url(r'/news', NewsCreate, name='news_create'),
            url(r'/news/([0-9a-f]{32})', News, name='news'),
            url(r'/event', EventCreate, name='event_create'),
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
            url(r'/admin/search_fields', SearchFields, name='search_fields'),
            url(r'/admin/statuses', Statuses, name='statuses'),
            url(r'/admin/config', Config, name='config'),
            ]

def main():
    logging.info("OrderPortal version %s", orderportal.__version__)
    if settings['TORNADO_DEBUG']:
        logging.info('tornado debug')
    if settings['LOGGING_DEBUG']:
        logging.info('logging debug')
    handlers = get_handlers()
    try:
        handlers.append(tornado.web.url(r'/site/([^/]+)',
                                        tornado.web.StaticFileHandler,
                                        {'path': settings['SITE_DIR']},
                                        name='site'))
    except KeyError:
        pass
    application = tornado.web.Application(
        handlers=handlers,
        debug=settings.get('TORNADO_DEBUG', False),
        cookie_secret=settings['COOKIE_SECRET'],
        ui_modules=uimodules,
        template_path='html',
        static_path='static',
        login_url=r'/login')
    application.listen(settings['PORT'], xheaders=True)
    logging.info("web server PID %s on port %s", os.getpid(), settings['PORT'])
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    parser = utils.get_command_line_parser(description='Web app server.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    main()
