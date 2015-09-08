"OrderPortal: Order pages."

from __future__ import print_function, absolute_import

import logging
import urlparse

import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def update_fields(self, fields):
        "Update all fields from the HTML form input."
        assert self.rqh is not None
        # Loop over fields defined in the form document and get values.
        # Do not change values for a field if that argument is missing.
        docfields = self.doc['fields']
        for field in fields:
            if field['type'] == constants.GROUP: continue

            identifier = field['identifier']
            try:
                value = self.rqh.get_argument(identifier) or None
                if value == '__none__': value = None
            except tornado.web.MissingArgumentError:
                pass
            else:
                if value != docfields.get(identifier):
                    changed = self.changed.setdefault('fields', dict())
                    changed[identifier] = value
                    docfields[identifier] = value
        self.check_fields_validity(fields)

    def check_fields_validity(self, fields):
        "Check validity of current values."
        self.doc['invalid'] = dict()
        for field in fields:
            if field['depth'] == 0:
                self.check_validity(field)

    def check_validity(self, field):
        """Check validity of converted field values.
        Skip field if not visible.
        Else check recursively, postorder.
        """
        logging.debug("field %s %s", field['identifier'], field['type'])
        message = None
        select_id = field.get('visible_if_select_field')
        if select_id:
            select_value = self.doc['fields'].get(select_id)
            if select_value != field.get('visible_if_select_value'):
                return True

        if field['type'] == constants.GROUP:
            for subfield in field['fields']:
                if not self.check_validity(subfield):
                    message = 'subfield(s) invalid'
        else:
            value = self.doc['fields'][field['identifier']]
            if value is None:
                if field['required']:
                    message = 'missing value'
            elif field['type'] == constants.INT:
                try:
                    self.doc['fields'][field['identifier']] = int(value)
                except (TypeError, ValueError):
                    message = 'not an integer value'
            elif field['type'] == constants.FLOAT:
                try:
                    self.doc['fields'][field['identifier']] = float(value)
                except (TypeError, ValueError):
                    message = 'not a float value'
            elif field['type'] == constants.BOOLEAN:
                logging.debug("boolean %s", value)
                try:
                    if value is None: raise ValueError
                    self.doc['fields'][field['identifier']] = utils.to_bool(value)
                except (TypeError, ValueError):
                    message = 'not a boolean value'
            elif field['type'] == constants.URL:
                parsed = urlparse.urlparse(value)
                if not (parsed.scheme and parsed.netloc):
                    message = 'incomplete URL'
            elif field['type'] == constants.SELECT:
                if value not in field['select']:
                    message = 'invalid selection'
        if message:
            self.doc['invalid'][field['identifier']] = message
        return message is None


class OrderMixin(object):
    "Mixin for various useful methods."

    def is_editable(self, order):
        "Is the order editable by the current user?"
        if self.is_admin(): return True
        status = self.get_order_status(order)
        edit = status.get('edit', [])
        if self.is_staff() and constants.STAFF in edit: return True
        if self.is_owner(order) and constants.USER in edit: return True
        return False

    def check_readable(self, order):
        "Check if current user may read the order."
        if self.is_owner(order): return
        if self.is_staff(): return
        raise tornado.web.HTTPError(403, reason='you may not read the order')

    def check_editable(self, order):
        "Check if current user may edit the order."
        if self.is_editable(order): return
        raise tornado.web.HTTPError(403, reason='you may not edit the order')

    def get_order_status(self, order):
        "Get the order status lookup."
        return settings['ORDER_STATUSES_LOOKUP'][order['status']]

    def get_targets(self, order):
        "Get the allowed transition targets."
        result = []
        for transition in settings['ORDER_TRANSITIONS']:
            if transition['source'] != order['status']: continue
            # Check validity
            if transition.get('require') == 'valid' and order['invalid']:
                continue
            permission = transition['permission']
            if (self.is_admin() and constants.ADMIN in permission) or \
               (self.is_staff() and constants.STAFF in permission) or \
               (self.is_owner(order) and constants.USER in permission):
                result.extend(transition['targets'])
        return [settings['ORDER_STATUSES_LOOKUP'][t] for t in result]


class Orders(RequestHandler):
    "Page for a list of all orders."

    @tornado.web.authenticated
    def get(self):
        if not self.is_staff():
            self.see_other('orders_account', self.current_user['email'])
        params = dict()
        # Filter list
        status = self.get_argument('status', '')
        if status:
            params['status'] = status
            view = self.db.view('order/status',
                                startkey=[status, constants.HIGH_CHAR],
                                endkey=[status],
                                descending=True,
                                include_docs=True)
        else:
            view = self.db.view('order/modified',
                                descending=True,
                                include_docs=True)
        orders = [self.get_presentable(r.doc) for r in view]
        # Page
        count = len(orders)
        max_page = (count - 1) / constants.PAGE_SIZE
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * constants.PAGE_SIZE
        end = min(start + constants.PAGE_SIZE, count)
        orders = orders[start : end]
        params['page'] = page
        self.render('orders.html',
                    orders=orders,
                    params=params,
                    start=start+1,
                    end=end,
                    max_page=max_page,
                    count=count)


class OrdersAccount(RequestHandler):
    "Page for a list of all orders for an account."

    @tornado.web.authenticated
    def get(self, email):
        if not self.is_staff() and email != self.current_user['email']:
            raise tornado.web.HTTPError(403,
                                        reason='you may not view these orders')
        account = self.get_account(email)
        view = self.db.view('order/owner',
                            include_docs=True,
                            key=email)
        orders = [self.get_presentable(r.doc) for r in view]
        orders.sort(lambda i, j: cmp(i['modified'], j['modified']),
                    reverse=True)
        self.render('orders_account.html', account=account, orders=orders)


class Order(OrderMixin, RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        title = order.get('title') or order['_id']
        self.render('order.html',
                    title="Order '{}'".format(title),
                    order=order,
                    status=self.get_order_status(order),
                    fields=form['fields'],
                    is_editable=self.is_admin() or self.is_editable(order),
                    targets=self.get_targets(order))

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        self.delete_logs(order['_id'])
        self.db.delete(order)
        self.see_other('orders')


class OrderLogs(OrderMixin, RequestHandler):
    "Order log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        self.render('logs.html',
                    title="Logs for order '{}'".format(order['title']),
                    entity=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Create a new order."

    @tornado.web.authenticated
    def get(self):
        form = self.get_entity(self.get_argument('form'),doctype=constants.FORM)
        self.render('order_create.html', form=form)

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        form = self.get_entity(self.get_argument('form'),doctype=constants.FORM)
        fields = Fields(form)
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = self.get_argument('title', None) or form['title']
            saver['fields'] = dict([(f['identifier'], None) for f in fields])
            saver['invalid'] = dict()
            saver['owner'] = self.current_user['email']
            for transition in settings['ORDER_TRANSITIONS']:
                if transition['source'] is None:
                    saver['status'] = transition['targets'][0]
                    break
            else:
                raise ValueError('no initial order status defined')
            saver.check_fields_validity(fields)
        self.see_other('order', saver.doc['_id'])


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        self.render('order_edit.html',
                    title="Edit order '{}'".format(order['title']),
                    order=order,
                    fields=form['fields'])

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        with OrderSaver(doc=order, rqh=self) as saver:
            saver['title'] = self.get_argument('__title__', order['_id'])
            saver.update_fields(Fields(form))
        if self.get_argument('save', None) == 'continue':
            self.see_other('order_edit', order['_id'])
        else:
            self.see_other('order', order['_id'])


class OrderTransition(OrderMixin, RequestHandler):
    "Change the status of an order."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        for target in self.get_targets(order):
            if target['identifier'] == targetid: break
        else:
            raise tornado.web.HTTPError(403, reason='invalid target')
        with OrderSaver(doc=order, rqh=self) as saver:
            saver['status'] = targetid
        self.see_other('order', order['_id'])
