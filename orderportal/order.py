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
                pass            # Missing arg means no change,
                                # which is not the same as value None!
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
        message = None
        select_id = field.get('visible_if_field')
        if select_id:
            select_value = str(self.doc['fields'].get(select_id)).lower()
            if select_value != str(field.get('visible_if_value')).lower():
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

    def is_readable(self, order):
        "Is the order readable by the current user?"
        if self.is_owner(order): return True
        if self.is_staff(): return True
        if self.is_colleague(order['owner']): return True
        return False

    def check_readable(self, order):
        "Check if current user may read the order."
        if self.is_readable(order): return
        raise tornado.web.HTTPError(403, reason='you may not read the order')

    def is_editable(self, order):
        "Is the order editable by the current user?"
        if self.is_admin(): return True
        status = self.get_order_status(order)
        edit = status.get('edit', [])
        if self.is_staff() and constants.STAFF in edit: return True
        if self.is_owner(order) and constants.USER in edit: return True
        return False

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

    def is_clonable(self, order):
        "Can the given order be cloned? Its form must be enabled."
        form = self.get_entity(order['form'], doctype=constants.FORM)
        return form['status'] == constants.ENABLED


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
        orders = [r.doc for r in view]
        # Page
        page_size = self.current_user.get('page_size') or constants.DEFAULT_PAGE_SIZE
        count = len(orders)
        max_page = (count - 1) / page_size
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * page_size
        end = min(start + page_size, count)
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

    def is_readable(self, account):
        "Is the account readable by the current user?"
        if account['email'] == self.current_user['email']: return True
        if self.is_staff(): return True
        if self.is_colleague(account['email']): return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.is_readable(account): return
        raise tornado.web.HTTPError(403, reason='you may not view these orders')

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_readable(account)
        view = self.db.view('order/owner',
                            include_docs=True,
                            key=email)
        orders = [r.doc for r in view]
        params = dict()
        # Filter list
        status = self.get_argument('status', '')
        if status:
            params['status'] = status
            orders = [o for o in orders if o.get('status') == status]
        orders.sort(lambda i, j: cmp(i['modified'], j['modified']),
                    reverse=True)
        self.render('orders_account.html',
                    account=account,
                    orders=orders,
                    params=params)


class OrdersGroups(RequestHandler):
    "Page for a list of all orders for the groups of an account."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        if not (self.is_staff() or email == self.current_user['email']):
            raise tornado.web.HTTPError(403,
                                        reason='you may not view these orders')
        orders = []
        view = self.db.view('order/owner', include_docs=True)
        for colleague in self.get_account_colleagues(email):
            orders.extend([r.doc for r in view[colleague]])
        params = dict()
        # Filter list
        status = self.get_argument('status', '')
        if status:
            params['status'] = status
            orders = [o for o in orders if o.get('status') == status]
        orders.sort(lambda i, j: cmp(i['modified'], j['modified']),
                    reverse=True)
        self.render('orders_groups.html',
                    account=account,
                    orders=orders,
                    params=params)


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
                    form=form,
                    fields=form['fields'],
                    is_editable=self.is_admin() or self.is_editable(order),
                    is_clonable=self.is_clonable(order),
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
            for status in settings['ORDER_STATUSES']:
                if status.get('initial'):
                    saver['status'] = status['identifier']
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
        colleagues = sorted(self.get_account_colleagues(self.current_user['email']))
        form = self.get_entity(order['form'], doctype=constants.FORM)
        self.render('order_edit.html',
                    title="Edit order '{}'".format(order['title']),
                    order=order,
                    colleagues=colleagues,
                    fields=form['fields'])

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        try:
            with OrderSaver(doc=order, rqh=self) as saver:
                saver['title'] = self.get_argument('__title__', order['_id'])
                try:
                    owner = self.get_argument('__owner__')
                    account = self.get_account(owner)
                    if account.get('status') != constants.ENABLED:
                        raise ValueError('owner account is not enabled')
                except tornado.web.MissingArgumentError:
                    pass
                except tornado.web.HTTPError:
                    raise ValueError('no such owner account')
                else:
                    saver['owner'] = account['email']
                saver.update_fields(Fields(form))
            if self.get_argument('__save__', None) == 'continue':
                self.see_other('order_edit', order['_id'])
            else:
                self.see_other('order', order['_id'])
        except ValueError, msg:
            self.see_other('order_edit', order['_id'], error=str(msg))


class OrderClone(OrderMixin, RequestHandler):
    "Create a new order from an existing one."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        if form['status'] != constants.ENABLED:
            raise ValueError('This order is outdated; the form of it has been disabled.')
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = "Clone of {}".format(order['title'])
            saver['fields'] = order['fields'].copy()
            for status in settings['ORDER_STATUSES']:
                if status.get('initial'):
                    saver['status'] = status['identifier']
                    break
            else:
                raise ValueError('no initial order status defined')
            saver.check_fields_validity(Fields(form))
        self.see_other('order', saver.doc['_id'])


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


class OrderFile(RequestHandler):
    "File attached to an order."

    @tornado.web.authenticated
    def get(self, iuid, filename):
        pass

    @tornado.web.authenticated
    def post(self, iuid, filename=None):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, filename)
            return

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        self.db.delete_attachment(order, filename)
        utils.log(self.db, self, order, changed=dict('file_deleted', filename))
        self.see_other('order', order['_id'])
