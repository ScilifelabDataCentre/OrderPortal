"OrderPortal: Order pages."

from __future__ import print_function, absolute_import

import cStringIO
import logging
import re
import urlparse

import tornado.web

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.fields import Fields
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def set_identifier(self, form):
        """Set the order identifier if format defined.
        Only if form is enabled; not when testing."""
        if form['status'] != constants.ENABLED: return
        try:
            fmt = settings['ORDER_IDENTIFIER_FORMAT']
        except KeyError:    # No identifier; sequential counter not used
            pass
        else:               # Identifier; sequential counter is used
            counter = self.rqh.get_next_counter(constants.ORDER)
            self['identifier'] = fmt.format(counter)

    def set_status(self, new):
        self['status'] = new
        self.doc['history'][new] = utils.today()

    def update_fields(self, fields):
        "Update all fields from the HTML form input."
        assert self.rqh is not None
        # Loop over fields defined in the form document and get values.
        # Do not change values for a field if that argument is missing,
        # except for checkbox, in which case missing value means False.
        docfields = self.doc['fields']
        for field in fields:
            try:
                if field['type'] == constants.GROUP: continue

                identifier = field['identifier']
                try:
                    value = self.rqh.get_argument(identifier)
                    if value == '': value = None
                except tornado.web.MissingArgumentError:
                    # Missing arg means no change,
                    # which is not same as value None!
                    # Except for boolean checkbox:
                    if field['type'] == constants.BOOLEAN and field.get('checkbox'):
                        value = False
                    else:
                        continue
                if value != docfields.get(identifier):
                    changed = self.changed.setdefault('fields', dict())
                    changed[identifier] = value
                    docfields[identifier] = value
            except ValueError, msg:
                raise ValueError(u"{0} field {1}".
                                 format(msg, field['identifier']))
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
            select_value = self.doc['fields'].get(select_id)
            if select_value: select_value = select_value.lower()
            if_value = field.get('visible_if_value')
            if if_value: if_value = if_value.lower()
            if select_value != if_value: return True

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
        if not hasattr(self, 'file'): return
        # Using cStringIO here is a kludge.
        # Don't ask me why this was required on one machine, but not another.
        # The problem appeared on a Python 2.6 system, and involved Unicode.
        # But I was unable to isolate it. I tested this in desperation...
        self.db.put_attachment(self.doc,
                               cStringIO.StringIO(self.file.body),
                               filename=self.file.filename,
                               content_type=self.file.content_type)

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
        if not self.global_modes['allow_order_editing']: return False
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
        "Get the allowed status transition targets."
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
        if not self.global_modes['allow_order_creation']: return False
        form = self.get_entity(order['form'], doctype=constants.FORM)
        return form['status'] in (constants.ENABLED, constants.TESTING)

    def prepare_message(self, order):
        "Prepare a message to send after status change."
        try:
            template = settings['ORDER_MESSAGES'][order['status']]
        except KeyError:
            return
        owner = self.get_account(order['owner'])
        # Owner account may have disappeared; not very likely...
        if owner and 'owner' in template['recipients']:
            recipients = set([owner['email']])
        else:
            recipients = set()
        if 'group' in template['recipients']:
            recipients.update([a['email']
                               for a in self.get_colleagues(owner['email'])])
        if 'admin' in template['recipients']:
            recipients.update([a['email'] for a in self.get_admins()])
        with MessageSaver(rqh=self) as saver:
            saver.set_params(
                owner=order['owner'],
                title=order['title'],
                identifier=order.get('identifier') or order['_id'],
                url=self.order_reverse_url(order))
            saver.set_template(template)
            saver['recipients'] = list(recipients)


class Orders(RequestHandler):
    "Orders list page; just HTML, Datatables obtains data via API call."

    @tornado.web.authenticated
    def get(self):
        "Ordinary users are not allowed to see the overall orders list."
        if not self.is_staff():
            self.see_other('account_orders', self.current_user['email'])
            return
        order_column = 5 + len(settings['ORDERS_LIST_STATUSES']) + \
            len(settings['ORDERS_LIST_FIELDS'])
        self.render('orders.html',
                    forms=self.get_forms(),
                    order_column=order_column,
                    params=self.get_filter_params())

    def get_filter_params(self):
        "Return a dictionary with the given filter parameters."
        result = dict()
        for key in ['status', 'form'] + \
                   [f['identifier'] for f in settings['ORDERS_LIST_FIELDS']]:
            try:
                value = self.get_argument(key)
                if not value: raise KeyError
                result[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass
        recent = self.get_argument('recent', None)
        if recent is None:
            recent = True
        else:
            try:
                recent = utils.to_bool(recent)
            except ValueError:
                recent = True
        result['recent'] = recent
        return result


class ApiV1Orders(Orders):
    "Orders API; JSON output."

    @tornado.web.authenticated
    def get(self):
        "JSON output."
        self.check_staff()
        orders = self.get_orders()
        names = self.get_account_names(None)
        # Forms lookup on iuid
        forms = dict([(f[1], f[0]) for f in self.get_forms(enabled=False)])
        data = []
        for order in orders:
            item = dict(title=order['title'],
                        form_title=forms[order['form']],
                        form_href=self.reverse_url('form', order['form']),
                        owner_name=names[order['owner']],
                        owner_href=self.reverse_url('account', order['owner']),
                        fields={},
                        status=order['status'].capitalize(),
                        status_href=
                            self.reverse_url('site', order['status'] + '.png'),
                        history={},
                        modified=order['modified'])
            item['href'] = self.order_reverse_url(order)
            identifier = order.get('identifier')
            if not identifier:
                identifier = order['_id'][:6] + '...'
            item['identifier'] = identifier
            for f in settings['ORDERS_LIST_FIELDS']:
                item['fields'][f['identifier']] = order['fields'].get(f['identifier'])
            for s in settings['ORDERS_LIST_STATUSES']:
                item['history'][s] = order['history'].get(s)
            data.append(item)
        self.write(dict(data=data))

    def get_orders(self):
        params = self.get_filter_params()
        orders = self.filter_by_status(params.get('status'))
        orders = self.filter_by_form(params.get('form'), orders=orders)
        for f in settings['ORDERS_LIST_FIELDS']:
            orders = self.filter_by_field(f['identifier'],
                                          params.get(f['identifier']),
                                          orders=orders)
        # No filter; all orders
        if orders is None:
            view = self.db.view('order/modified',
                                include_docs=True,
                                descending=True)
            orders = [r.doc for r in view]
        if settings['ORDERS_DISPLAY_MOST_RECENT'] > 0:
            if params.get('recent', True):
                orders = orders[:settings['ORDERS_DISPLAY_MOST_RECENT']]
        return orders

    def filter_by_status(self, status, orders=None):
        "Return orders list if any status filter, or None if none."
        if status:
            if orders is None:
                view = self.db.view('order/status',
                                    descending=True,
                                    startkey=[status, constants.CEILING],
                                    endkey=[status],
                                    reduce=False,
                                    include_docs=True)
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o['status'] == status]
        return orders

    def filter_by_form(self, form, orders=None):
        "Return orders list if any form filter, or None if none."
        if form:
            if orders is None:
                view = self.db.view('order/form',
                                    descending=True,
                                    startkey=[form, constants.CEILING],
                                    endkey=[form],
                                    reduce=False,
                                    include_docs=True)
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o['form'] == form]
        return orders

    def filter_by_field(self, identifier, value, orders=None):
        "Return orders list if any field filter, or None if none."
        if value:
            if orders is None:
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True)
                orders = [r.doc for r in view]
            if value == '__none__': value = None
            orders = [o for o in orders if o['fields'].get(identifier) == value]
        return orders


class Order(OrderMixin, RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            match = re.match(settings['ORDER_IDENTIFIER_REGEXP'], iuid)
            if not match: raise KeyError
        except KeyError:
            order = self.get_entity(iuid, doctype=constants.ORDER)
        else:
            order = self.get_entity_view('order/identifier', match.group())
        self.check_readable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
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
                    title=u"Order '{0}'".format(order['title']),
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
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(
            405, reason='internal problem; POST only allowed for DELETE')

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
                    title=u"Logs for order '{0}'".format(order['title']),
                    entity=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Create a new order. Redirect with error message if not logged in."

    def get(self):
        if not self.current_user:
            self.see_other('home',
                           error="You need to be logged in to create an order."
                           " Register to get an account if you don't have one.")
            return
        if not self.global_modes['allow_order_creation'] \
           and self.current_user['role'] != constants.ADMIN:
            self.see_other('home',error='Order creation is currently disabled.')
            return
        form = self.get_entity(self.get_argument('form'),doctype=constants.FORM)
        self.render('order_create.html', form=form)

    @tornado.web.authenticated
    def post(self):
        form = self.get_entity(self.get_argument('form'),doctype=constants.FORM)
        fields = Fields(form)
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = self.get_argument('title', None) or form['title']
            saver['fields'] = dict([(f['identifier'], None) for f in fields])
            saver['history'] = {}
            saver.set_status(settings['ORDER_STATUS_INITIAL']['identifier'])
            for target, source in settings['ORDER_AUTOPOPULATE'].iteritems():
                if target not in fields: continue
                value = self.current_user
                for key in source.split(':'):
                    value = value.get(key)
                    if value is None: break
                saver['fields'][target] = value
            saver.check_fields_validity(fields)
            saver.set_identifier(form)
        self.see_other('order_edit', saver.doc['_id'])


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        if not self.global_modes['allow_order_editing'] \
           and self.current_user['role'] != constants.ADMIN:
            self.see_other('home', error='Order editing is currently disabled.')
            return
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        colleagues = sorted(self.get_account_colleagues(self.current_user['email']))
        form = self.get_entity(order['form'], doctype=constants.FORM)
        self.render('order_edit.html',
                    title=u"Edit order '{0}'".format(order['title']),
                    order=order,
                    colleagues=colleagues,
                    form=form,
                    fields=form['fields'])

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        form = self.get_entity(order['form'], doctype=constants.FORM)
        try:
            with OrderSaver(doc=order, rqh=self) as saver:
                saver['title'] = self.get_argument('__title__', None) or '[no title]'
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
            flag = self.get_argument('__save__', None)
            if flag == 'continue':
                self.see_other('order_edit', order['_id'])
            elif flag == 'submit': # XXX Hard-wired, currently
                targets = self.get_targets(order)
                for target in targets:
                    if target['identifier'] == 'submitted':
                        with OrderSaver(doc=order, rqh=self) as saver:
                            saver.set_status('submitted')
                        self.prepare_message(order)
                        self.redirect(self.order_reverse_url(
                                order,
                                message='Order saved and submitted.'))
                        break
                else:
                        self.redirect(self.order_reverse_url(
                                order,
                                message='Order saved.',
                                error='Order could not be submitted due to'
                                ' invalid or missing values.'))
            else:
                self.redirect(
                    self.order_reverse_url(order, message='Order saved.'))
        except ValueError, msg:
            self.redirect(self.order_reverse_url(order, error=str(msg)))


class OrderClone(OrderMixin, RequestHandler):
    "Create a new order from an existing one."

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        if not self.is_clonable(order):
            raise ValueError('This order is outdated; its form has been disabled.')
        form = self.get_entity(order['form'], doctype=constants.FORM)
        fields = Fields(form)
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = u"Clone of {0}".format(order['title'])
            saver['fields'] = dict()
            for field in fields:
                id = field['identifier']
                if field.get('erase_on_clone'):
                    saver['fields'][id] = None
                else:
                    saver['fields'][id] = order['fields'][id]
            saver['history'] = {}
            saver.set_status(settings['ORDER_STATUS_INITIAL']['identifier'])
            saver.check_fields_validity(fields)
            saver.set_identifier(form)
        self.redirect(self.order_reverse_url(saver.doc))


class OrderTransition(OrderMixin, RequestHandler):
    "Change the status of an order."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_editable(order)
        for target in self.get_targets(order):
            if target['identifier'] == targetid: break
        else:
            raise tornado.web.HTTPError(
                403, reason='invalid order transition target')
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.set_status(targetid)
        self.prepare_message(order)
        self.redirect(self.order_reverse_url(order))


class OrderFile(OrderMixin, RequestHandler):
    "File attached to an order."

    @tornado.web.authenticated
    def get(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        outfile = self.db.get_attachment(order, filename)
        if outfile is None:
            self.write('')
        else:
            self.write(outfile.read())
            outfile.close()
        self.set_header('Content-Type',
                        order['_attachments'][filename]['content_type'])
        self.set_header('Content-Disposition',
                        'attachment; filename="{0}"'.format(filename))

    @tornado.web.authenticated
    def post(self, iuid, filename):
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, filename)
            return
        raise tornado.web.HTTPError(
            405, reason='internal problem; POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.delete_filename = filename
        self.redirect(self.order_reverse_url(order))


class OrderAttach(OrderMixin, RequestHandler):
    "Attach a file to an order."

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        try:
            infile = self.request.files['file'][0]
        except (KeyError, IndexError):
            pass
        else:
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.file = infile
                saver['filename'] = infile.filename
                saver['size'] = len(infile.body)
                saver['content_type'] = infile.content_type or 'application/octet-stream'
        self.redirect(self.order_reverse_url(order))
