"OrderPortal: Order pages."

from __future__ import unicode_literals, print_function, absolute_import

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.requesthandler import RequestHandler


class OrderSaver(saver.Saver):
    doctype = constants.ORDER


class Orders(RequestHandler):
    "Orders list page."

    @tornado.web.authenticated
    def get(self):
        if self.is_staff():
            view = self.db.view('order/modified', include_docs=True)
            title = 'Recent orders'
        else:
            view = self.db.view('order/owner', include_docs=True,
                                key=self.current_user['email'])
            title = 'Your orders'
        orders = [self.get_presentable(r.doc) for r in view]
        self.render('orders.html', title=title, orders=orders)


class Order(RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        # XXX Check read privilege
        self.render('order.html',
                    title="Order '{}'".format(order['title']),
                    order=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Page for creating an order."

    @tornado.web.authenticated
    def get(self):
        self.render('order_create.html', title='Create a new order')

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        with OrderSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['description'] = self.get_argument('description', None)
            saver['owner'] = self.current_user['email']
            doc = saver.doc
        self.see_other(self.reverse_url('order', doc['_id']))
