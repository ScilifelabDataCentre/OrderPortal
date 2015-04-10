"OrderPortal: Order pages."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.requesthandler import RequestHandler


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def update_fields(self):
        "Update all fields from the HTML form input."
        assert self.rqh is not None
        for field in self.rqh._flatten_fields(self.doc['fields']):
            identifier = field['identifier']
            old = field.get('value')
            value = self.rqh.get_argument(identifier, None)
            if old != value:
                changed = self.changed.setdefault('field_values', dict())
                changed[identifier] = value
                field['value'] = value


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
        self.check_read_order(order)
        self.render('order.html',
                    title="Order '{}'".format(order['title']),
                    order=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Page for creating an order."

    @tornado.web.authenticated
    def get(self):
        self.render('order_create.html',
                    title='Create a new order')

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        with OrderSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['fields'] = self.get_all_fields_sorted()
            saver['owner'] = self.current_user['email']
            doc = saver.doc
        self.see_other(self.reverse_url('order', doc['_id']))


class OrderEdit(RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_edit_order(order)
        self.render('order_edit.html',
                    title="Edit order '{}'".format(order['title']),
                    order=order)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_edit_order(order)
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.update_fields()
        self.see_other(self.reverse_url('order', order['_id']))
