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

    def post_process(self):
        "Save or delete the file as an attachment to the document."
        # Try deleting file.
        try:
            filename = self.delete_filename
        except AttributeError:
            pass
        else:
            self.db.delete_attachment(self.doc, filename)
            self.changed['file_deleted'] = filename
            return
        # No new file uploaded, just skip out.
        try:
            if self.content is None: return
        except AttributeError:
            return
        self.db.put_attachment(self.doc,
                               self.content,
                               filename=self['filename'],
                               content_type=self['content_type'])

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

    def is_attachable(self, order):
        "Check if the current user may attach a file to the order."
        if self.is_admin(): return True
        status = self.get_order_status(order)
        edit = status.get('attach', [])
        if self.is_staff() and constants.STAFF in edit: return True
        if self.is_owner(order) and constants.USER in edit: return True
        return False

    def check_attachable(self, order):
        "Check if current user may attach a file to the order."
        if self.is_attachable(order): return
        raise tornado.web.HTTPError(
            403, reason='you may not attach a file to the order')

    def get_order_status(self, order):
        "Get the order status lookup item."
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
        return form['status'] in (constants.ENABLED, constants.TESTING)


class Orders(RequestHandler):
    "Page for a list of all orders."

    @tornado.web.authenticated
    def get(self):
        if not self.is_staff():
            self.see_other('account_orders', self.current_user['email'])
        params = dict()
        # Filter for status
        status = self.get_argument('status', '')
        if status:
            view = self.db.view('order/status',
                                startkey=[status],
                                endkey=[status, constants.CEILING])
            params['status'] = status
        # No filter
        else:
            view = self.db.view('order/owner')
        page = self.get_page(view=view)
        # Filter for status
        if status:
            view = self.db.view('order/status',
                                reduce=False,
                                include_docs=True,
                                descending=True,
                                startkey=[status, constants.CEILING],
                                endkey=[status],
                                skip=page['start'],
                                limit=page['size'])
        # No filter
        else:
            view = self.db.view('order/modified',
                                include_docs=True,
                                descending=True,
                                skip=page['start'],
                                limit=page['size'])
        orders = [r.doc for r in view]
        account_names = self.get_account_names([o['owner'] for o in orders])
        self.render('orders.html',
                    orders=orders,
                    account_names=account_names,
                    params=params,
                    page=page)


class Order(OrderMixin, RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        title = order.get('title') or order['_id']
        files = []
        if self.is_attachable(order):
            for filename in order.get('_attachments', []):
                stub = order['_attachments'][filename]
                files.append(dict(filename=filename,
                                  size=stub['length'],
                                  content_type=stub['content_type']))
                files.sort(lambda i,j: cmp(i['filename'].lower(),
                                           j['filename'].lower()))
        self.render('order.html',
                    title="Order '{0}'".format(title),
                    order=order,
                    account_names=self.get_account_names([order['owner']]),
                    status=self.get_order_status(order),
                    form=form,
                    fields=form['fields'],
                    attached_files=files,
                    is_editable=self.is_admin() or self.is_editable(order),
                    is_clonable=self.is_clonable(order),
                    is_attachable=self.is_attachable(order),
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
                    title="Logs for order '{0}'".format(order['title']),
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
        self.see_other('order_edit', saver.doc['_id'])


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        colleagues = sorted(self.get_account_colleagues(self.current_user['email']))
        form = self.get_entity(order['form'], doctype=constants.FORM)
        self.render('order_edit.html',
                    title="Edit order '{0}'".format(order['title']),
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
        if not self.is_clonable(order):
            raise ValueError('This order is outdated; its form has been disabled.')
        form = self.get_entity(order['form'], doctype=constants.FORM)
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = "Clone of {0}".format(order['title'])
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


class OrderFile(OrderMixin, RequestHandler):
    "File attached to an order."

    @tornado.web.authenticated
    def get(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        infile = self.db.get_attachment(order, filename)
        if infile is None:
            self.write('')
        else:
            self.write(infile.read())
            infile.close()
        self.set_header('Content-Type',
                        order['_attachments'][filename]['content_type'])
        self.set_header('Content-Disposition',
                        'attachment; filename="{0}"'.format(filename))

    @tornado.web.authenticated
    def post(self, iuid, filename):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, filename)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.delete_filename = filename
        self.see_other('order', order['_id'])


class OrderAttach(OrderMixin, RequestHandler):
    "Attach a file to an order."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        try:
            infile = self.request.files['file'][0]
        except (KeyError, IndexError):
            pass
        else:
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.content = infile['body']
                saver['filename'] = infile['filename']
                saver['size'] = len(saver.content)
                saver['content_type'] = infile['content_type'] or 'application/octet-stream'
        self.see_other('order', order['_id'])
