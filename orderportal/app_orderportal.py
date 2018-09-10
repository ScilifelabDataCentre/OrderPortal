#!/usr/bin/python2
"OrderPortal web application server."

from __future__ import print_function, absolute_import

import logging
import os
import sys

import tornado.web
import tornado.ioloop

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


def main():
    parser = utils.get_command_line_parser(description='OrderPortal server.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings)

    url = tornado.web.url
    handlers = [url(r'/', Home, name='home')]
    try:
        regexp = settings['ORDER_IDENTIFIER_REGEXP']
    except KeyError:
        pass
    else:
        handlers.append(url(r"/order/({0})".format(regexp),
                            Order, name='order_id'))
        handlers.append(url(r"/api/v1/order/({0})".format(regexp),
                            OrderApiV1, name='order_id_api'))

    handlers.extend([
        url(r'/order/([0-9a-f]{32})', Order, name='order'),
        url(r'/api/v1/order/([0-9a-f]{32})', OrderApiV1, name='order_api'),
        url(r'/order/([^/]+).csv', OrderCsv, name='order_csv'),
        url(r'/order/([^/]+).zip', OrderZip, name='order_zip'),
        url(r'/order/([0-9a-f]{32})/logs', OrderLogs, name='order_logs'),
        url(r'/order', OrderCreate, name='order_create'),
        url(r'/api/v1/order', OrderCreateApiV1, name='order_create_api'),
        url(r'/order/([0-9a-f]{32})/edit', OrderEdit, name='order_edit'),
        url(r'/order/([0-9a-f]{32})/transition/(\w+)',
            OrderTransition, name='order_transition'),
        url(r'/api/v1/order/([0-9a-f]{32})/transition/(\w+)',
            OrderTransitionApiV1, name='order_transition_api'),
        url(r'/order/([0-9a-f]{32})/clone', OrderClone, name='order_clone'),
        url(r'/order/([0-9a-f]{32})/file', OrderFile, name='order_file_add'),
        url(r'/order/([0-9a-f]{32})/file/([^/]+)',OrderFile,name='order_file'),
        url(r'/order/([0-9a-f]{32})/report', OrderReport, name='order_report'),
        url(r'/api/v1/order/([0-9a-f]{32})/report',
            OrderReportApiV1, name='order_report_api'),
        url(r'/order/([0-9a-f]{32})/report/edit',
            OrderReportEdit, name='order_report_edit'),
        url(r'/orders', Orders, name='orders'),
        url(r'/api/v1/orders', OrdersApiV1, name='orders_api'),
        url(r'/orders.csv', OrdersCsv, name='orders_csv'),
        url(r'/accounts', Accounts, name='accounts'),
        url(r'/api/v1/accounts', AccountsApiV1, name='accounts_api'),
        url(r'/accounts.csv', AccountsCsv, name='accounts_csv'),
        url(r'/account/([^/]+)', Account, name='account'),
        url(r'/api/v1/account/([^/]+)', AccountApiV1, name='account_api'),
        url(r'/account/([^/]+)/orders', AccountOrders, name='account_orders'),
        url(r'/api/v1/account/([^/]+)/orders',
            AccountOrdersApiV1, name='account_orders_api'),
        url(r'/account/([^/]+)/groups/orders',
            AccountGroupsOrders, name='account_groups_orders'),
        url(r'/api/v1/account/([^/]+)/groups/orders',
            AccountGroupsOrdersApiV1, name='account_groups_orders_api'),
        url(r'/account/([^/]+)/logs', AccountLogs, name='account_logs'),
        url(r'/account/([^/]+)/messages',
            AccountMessages, name='account_messages'),
        url(r'/account/([^/]+)/edit', AccountEdit, name='account_edit'),
        url(r'/group', GroupCreate, name='group_create'),
        url(r'/group/([0-9a-f]{32})', Group, name='group'),
        url(r'/group/([0-9a-f]{32})/edit', GroupEdit, name='group_edit'),
        url(r'/group/([0-9a-f]{32})/accept', GroupAccept, name='group_accept'),
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
        url(r'/registered', Registered, name='registered'),
        url(r'/account/([^/]+)/enable', AccountEnable, name='account_enable'),
        url(r'/account/([^/]+)/disable', AccountDisable,name='account_disable'),
        url(r'/account/([^/]+)/updateinfo',
            AccountUpdateInfo, name='account_update_info'),
        url(r'/forms', Forms, name='forms'),
        url(r'/form/([0-9a-f]{32})', Form, name='form'),
        url(r'/api/v1/form/([0-9a-f]{32})', FormApiV1, name='form_api'),
        url(r'/form/([0-9a-f]{32})/logs', FormLogs, name='form_logs'),
        url(r'/form', FormCreate, name='form_create'),
        url(r'/form/([0-9a-f]{32})/edit', FormEdit, name='form_edit'),
        url(r'/form/([0-9a-f]{32})/clone', FormClone, name='form_clone'),
        url(r'/form/([0-9a-f]{32})/pending', FormPending, name='form_pending'),
        url(r'/form/([0-9a-f]{32})/testing', FormTesting, name='form_testing'),
        url(r'/form/([0-9a-f]{32})/enable', FormEnable, name='form_enable'),
        url(r'/form/([0-9a-f]{32})/disable', FormDisable, name='form_disable'),
        url(r'/form/([0-9a-f]{32})/field', FormFieldCreate,name='field_create'),
        url(r'/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)',
            FormFieldEdit, name='field_edit'),
        url(r'/form/([0-9a-f]{32})/field/([a-zA-Z][_a-zA-Z0-9]*)/descr',
            FormFieldEditDescr, name='field_edit_descr'),
        url(r'/form/([0-9a-f]{32})/orders', FormOrders, name='form_orders'),
        url(r'/form/([0-9a-f]{32})/orders.csv', 
            FormOrdersCsv, name='form_orders_csv'),
        url(r'/news', News, name='news'),
        url(r'/new/([0-9a-f]{32})', NewsEdit, name='news_edit'),
        url(r'/new', NewsCreate, name='news_create'),
        url(r'/events', Events, name='events'),
        url(r'/event/([0-9a-f]{32})', Event, name='event'),
        url(r'/event', EventCreate, name='event_create'),
        url(r'/contact', Contact, name='contact'),
        url(r'/about', About, name='about'),
        url(r'/software', Software, name='software'),
        url(r'/infos', Infos, name='infos'),
        url(r'/info', InfoCreate, name='info_create'),
        url(r'/info/([^/]+)', Info, name='info'),
        url(r'/info/([^/]+)/edit', InfoEdit, name='info_edit'),
        url(r'/info/([^/]+)/logs', InfoLogs, name='info_logs'),
        url(r'/files', Files, name='files'),
        url(r'/file', FileCreate, name='file_create'),
        url(r'/file/([^/]+)', File, name='file'),
        url(r'/file/([^/]+)/meta', FileMeta, name='file_meta'),
        url(r'/file/([^/]+)/download', FileDownload, name='file_download'),
        url(r'/file/([^/]+)/edit', FileEdit, name='file_edit'),
        url(r'/api/v1/file/([^/]+)/edit', FileEditApiV1, name='file_edit_api'),
        url(r'/file/([0-9a-f]{32})/logs', FileLogs, name='file_logs'),
        url(r'/log/([0-9a-f]{32})', Log, name='log'),
        url(r'/([0-9a-f]{32})', Entity, name='entity'),
        url(r'/admin/global_modes', GlobalModes, name='global_modes'),
        url(r'/admin/settings', Settings, name='settings'),
        url(r'/admin/text/([^/]+)', Text, name='text'),
        url(r'/admin/texts', Texts, name='texts'),
        url(r'/admin/order_statuses', OrderStatuses, name='order_statuses'),
        url(r'/admin/order_messages',
            AdminOrderMessages, name='admin_order_messages'),
        url(r'/admin/account_messages',
            AdminAccountMessages, name='admin_account_messages'),
        url(r'/site/([^/]+)', tornado.web.StaticFileHandler,
            {'path': utils.expand_filepath(settings['SITE_DIR'])},
            name='site'),
        url(r'/test', Test, name='test'),
        ])
    handlers.append(url(r'/api/v1/(.*)', NoSuchEntityApiV1))
    handlers.append(url(r'/(.*)', NoSuchEntity))
    application = tornado.web.Application(
        handlers=handlers,
        debug=settings.get('TORNADO_DEBUG', False),
        cookie_secret=settings['COOKIE_SECRET'],
        xsrf_cookies=True,
        ui_modules=uimodules,
        template_path=os.path.join(settings['ROOT_DIR'], 'html'),
        static_path=os.path.join(settings['ROOT_DIR'], 'static'),
        login_url=r'/login')
    # Add href URLs for the status icons.
    # This depends on order status setup.
    for key, value in settings['ORDER_STATUSES_LOOKUP'].iteritems():
        value['href'] = application.reverse_url('site', key + '.png')
    application.listen(settings['PORT'], xheaders=True)
    pid = os.getpid()
    logging.info("web server PID %s on port %s", pid, settings['PORT'])
    if options.pidfile:
        with open(options.pidfile, 'w') as pf:
            pf.write(str(pid))
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
