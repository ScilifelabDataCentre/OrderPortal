"OrderPortal: Order pages."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.fields import Fields
from orderportal.requesthandler import RequestHandler


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def update_fields(self):
        "Update all fields from the HTML form input."
        assert self.rqh is not None
        # for field in self.doc['fields']:
        #     identifier = field['identifier']
        #     old = field.get('value')
        #     value = self.rqh.get_argument(identifier, None)
        #     if old != value:
        #         changed = self.changed.setdefault('field_values', dict())
        #         changed[identifier] = value
        #         field['value'] = value


class Orders(RequestHandler):
    "Page for orders list and creating a new order from a form."

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
        forms = [self.get_presentable(r.doc) for r in
                 self.db.view('form/pending', include_docs=True)] # XXX enabled!
        self.render('orders.html', title=title, orders=orders, forms=forms)


class Order(RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_read_order(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        fields = Fields(form)
        title = order['fields'].get('title') or order['_id']
        self.render('order.html',
                    title="Order '{}'".format(title),
                    order=order,
                    fields=fields,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Create a new order."

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        form = self.get_entity(self.get_argument('form'),doctype=constants.FORM)
        fields = Fields(form)
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['fields'] = dict([(f['identifier'], None) for f in fields])
            saver['owner'] = self.current_user['email']
            for transition in settings['ORDER_TRANSITIONS']:
                if transition['source'] is None:
                    saver['status'] = transition['target'][0]
                    break
            saver['status'] = None
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
