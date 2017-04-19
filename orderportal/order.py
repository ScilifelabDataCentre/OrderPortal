"OrderPortal: Order pages."

from __future__ import print_function, absolute_import

import logging
from collections import OrderedDict as OD
from cStringIO import StringIO
import os.path
import re
import traceback
import urlparse

import tornado.web

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.fields import Fields
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler, ApiV1Mixin


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def setup(self):
        """Additional setup.
        1) Initialize flag for changed status.
        2) Prepare for attaching files.
        """
        self.changed_status = None
        self.files = []
        self.filenames = set(self.doc.get('_attachments', []))

    def add_file(self, infile):
        "Add the given file to the files. Return the unique filename."
        filename = infile.filename
        if filename in self.filenames:
            count = 1
            while True:
                filename, ext = os.path.splitext(infile.filename)
                filename = "{0}_{1}{2}".format(filename, count, ext)
                if filename not in self.filenames: break
                count += 1
        self.filenames.add(filename)
        self.files.append(dict(filename=filename,
                               body=infile.body,
                               content_type=infile.content_type))
        return filename

    def set_identifier(self, form):
        """Set the order identifier if format defined.
        Allow also for disabled, since admin may clone such orders."""
        if form['status'] not in (constants.ENABLED, constants.DISABLED): return
        try:
            fmt = settings['ORDER_IDENTIFIER_FORMAT']
        except KeyError:    # No identifier; sequential counter not used
            pass
        else:               # Identifier; sequential counter is used
            counter = self.rqh.get_next_counter(constants.ORDER)
            self['identifier'] = fmt.format(counter)

    def set_status(self, new, date=None):
        if self.get('status') == new: return
        self['status'] = new
        self.doc['history'][new] = date or utils.today()
        self.changed_status = new

    def update_fields(self):
        "Update all fields from the HTML form input."
        assert self.rqh is not None
        fields = Fields(self.rqh.get_entity(self.doc['form'],
                                            doctype=constants.FORM))
        docfields = self.doc['fields']
        self.removed_files = []       # Due to field update
        # Loop over fields defined in the form document and get values.
        # Do not change values for a field if that argument is missing,
        # except for checkbox, in which case missing value means False.
        for field in fields:
            # Field not displayed or not writeable must not be changed.
            if not self.rqh.is_staff() and \
                (field['restrict_read'] or field['restrict_write']): continue
            if field['type'] == constants.GROUP: continue
            identifier = field['identifier']
            if field['type'] == constants.FILE:
                try:
                    infile = self.rqh.request.files[identifier][0]
                except (KeyError, IndexError):
                    continue
                else:
                    value = self.add_file(infile)
                    self.removed_files.append(docfields.get(identifier))
            elif field['type'] == constants.MULTISELECT:
                value = self.rqh.get_arguments(identifier)
            elif field['type'] == constants.TABLE:
                value = docfields.get(identifier) or []
                for i, row in enumerate(value):
                    for j, item in enumerate(row):
                        key = "cell_{0}_{1}".format(i, j)
                        value[i][j] = self.rqh.get_argument(key, '')
                offset = len(value)
                for i in xrange(settings['ORDER_TABLE_NEW_ROWS']):
                    row = []
                    for j in xrange(len(field['table'])):
                        key = "cell_{0}_{1}".format(i+offset, j)
                        row.append(self.rqh.get_argument(key, ''))
                    value.append(row)
                # Remove empty rows
                value = [r for r in value if reduce(lambda x,y: x or y, r)]
            else:
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
        self.check_fields_validity(fields)

    def check_fields_validity(self, fields):
        "Check validity of current field values."
        self.doc['invalid'] = dict()
        for field in fields:
            if field['depth'] == 0:
                self.check_validity(field)

    def check_validity(self, field):
        """Check validity of field value. Convert for some field types.
        Execute the processor, if any.
        Skip field if not visible, else check recursively in postorder.
        Return True if valid, False otherwise.
        """
        docfields = self.doc['fields']
        try:
            select_id = field.get('visible_if_field')
            if select_id:
                select_value = docfields.get(select_id)
                if select_value is not None:
                    select_value = unicode(select_value).lower()
                if_value = field.get('visible_if_value')
                if if_value:
                    if_value = if_value.lower()
                if select_value != if_value: return True

            if field['type'] == constants.GROUP:
                for subfield in field['fields']:
                    if not self.check_validity(subfield):
                        raise ValueError('subfield(s) invalid')
            else:
                value = docfields[field['identifier']]
                if value is None:
                    if field['required']:
                        raise ValueError('missing value')
                elif field['type'] == constants.STRING:
                    pass
                elif field['type'] == constants.INT:
                    try:
                        docfields[field['identifier']] = int(value)
                    except (TypeError, ValueError):
                        raise ValueError('not an integer value')
                elif field['type'] == constants.FLOAT:
                    try:
                        docfields[field['identifier']] = float(value)
                    except (TypeError, ValueError):
                        raise ValueError('not a float value')
                elif field['type'] == constants.BOOLEAN:
                    try:
                        if value is None: raise ValueError
                        docfields[field['identifier']] = utils.to_bool(value)
                    except (TypeError, ValueError):
                        raise ValueError('not a boolean value')
                elif field['type'] == constants.URL:
                    parsed = urlparse.urlparse(value)
                    if not (parsed.scheme and parsed.netloc):
                        raise ValueError('incomplete URL')
                elif field['type'] == constants.SELECT:
                    if value not in field['select']:
                        raise ValueError('invalid selection')
                elif field['type'] == constants.MULTISELECT:
                    # Value is here always a list, no matter what.
                    if field['required'] and len(value) == 1 and value[0] == '':
                        raise ValueError('missing value')
                    for v in value:
                        if v and v not in field['multiselect']:
                            raise ValueError('value not among alternatives')
                elif field['type'] == constants.TEXT:
                    pass
                elif field['type'] == constants.DATE:
                    pass
                elif field['type'] == constants.TABLE:
                    pass
                elif field['type'] == constants.FILE:
                    pass
                processor = field.get('processor')
                if processor:
                    try:
                        processor = settings['PROCESSORS'][processor]
                    except KeyError:
                        raise ValueError("System error: No such processor '%s'"
                                         % processor)
                    else:
                        processor = processor(self.db, self.doc, field)
                        kwargs = dict()
                        if field['type'] == constants.FILE:
                            for file in self.files:
                                if file['filename'] == value:
                                    kwargs['body'] = file['body']
                                    kwargs['content_type']= file['content_type']
                                    break
                        processor.run(value, **kwargs)
        except ValueError, msg:
            self.doc['invalid'][field['identifier']] = str(msg)
            return False
        except Exception, msg:
            self.doc['invalid'][field['identifier']] = "System error: %s" % msg
            return False
        else:
            return True

    def post_process(self):
        self.modify_attachments()
        if self.changed_status:
            self.prepare_message()

    def modify_attachments(self):
        "Save or delete the file as an attachment to the document."
        try:                    # Delete the named file.
            self.db.delete_attachment(self.doc, self.delete_filename)
        except AttributeError:
            # Else add any new attached files.
            try:
                # First remove files due to field update
                for filename in self.removed_files:
                    if filename:
                        self.db.delete_attachment(self.doc, filename)
            except AttributeError:
                pass
            # Using cStringIO here is a kludge.
            # Don't ask me why this was required on a specific machine.
            # The problem appeared on a Python 2.6 system and involved
            # Unicode, but I was unable to isolate it.
            # I found this solution by chance...
            for file in self.files:
                self.db.put_attachment(self.doc,
                                       StringIO(file['body']),
                                       filename=file['filename'],
                                       content_type=file['content_type'])

    def prepare_message(self):
        """Prepare a message to send after status change.
        It is sent later by cron job script 'script/messenger.py'
        """
        try:
            template = settings['ORDER_MESSAGES'][self.doc['status']]
        except KeyError:
            return
        recipients = set()
        owner = self.get_account(self.doc['owner'])
        # Owner account may have been deleted.
        if owner:
            email = owner['email'].strip().lower()
            if 'owner' in template['recipients']:
                recipients = set([owner['email']])
            if 'group' in template['recipients']:
                for row in self.db.view('group/member',
                                        include_docs=True,
                                        key=email):
                    for member in row.doc['members']:
                        account = self.get_account(member)
                        if account and account['status'] == constants.ENABLED:
                            recipients.add(account['email'])
        if 'admin' in template['recipients']:
            view = self.db.view('account/role', include_docs=True)
            admins = [r.doc for r in view[constants.ADMIN]]
            for admin in admins:
                if admin['status'] == constants.ENABLED:
                    recipients.add(admin['email'])
        with MessageSaver(rqh=self) as saver:
            saver.set_params(
                owner=self.doc['owner'],
                title=self.doc['title'],
                identifier=self.doc.get('identifier') or self.doc['_id'],
                url=self.get_order_url(self.doc),
                tags=', '.join(self.doc.get('tags', [])))
            saver.set_template(template)
            saver['recipients'] = list(recipients)

    def get_order_url(self, order):
        """Member rqh is not available when used from a stand-alone script,
        so self.rqh.order_reverse_url cannot be used.
        The URL has to be synthesized explicitly here. """
        try:
            identifier = order['identifier']
        except KeyError:
            identifier = order['_id']
        path = "/order/{0}".format(identifier)
        return settings['BASE_URL'].rstrip('/') + path

    def get_account(self, email):
        "Get the account document for the given email."
        view = self.db.view('account/email', include_docs=True)
        rows = list(view[email])
        if len(rows) == 1:
            return rows[0].doc
        else:
            return None


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
        raise ValueError('You may not read the order.')

    def is_editable(self, order):
        "Is the order editable by the current user?"
        if self.is_admin(): return True
        if not self.global_modes['allow_order_editing']: return False
        status = self.get_order_status(order)
        edit = status.get('edit', [])
        if self.is_staff() and constants.STAFF in edit: return True
        if self.is_owner(order) and constants.USER in edit: return True
        return False

    def check_editable(self, order):
        "Check if current user may edit the order."
        if self.is_editable(order): return
        if not self.global_modes['allow_order_editing']:
            msg = '{0} editing is currently disabled.'
        else:
            msg = 'You may not edit the {0}.'
        raise ValueError(msg.format(utils.term('order')))

    def is_attachable(self, order):
        "Check if the current user may attach a file to the order."
        if self.is_admin(): return True
        status = self.get_order_status(order)
        attach = status.get('attach', [])
        if self.is_staff() and constants.STAFF in attach: return True
        if self.is_owner(order) and constants.USER in attach: return True
        return False

    def check_attachable(self, order):
        "Check if current user may attach a file to the order."
        if self.is_attachable(order): return
        raise tornado.web.HTTPError(
            403,
            reason="You may not attach a file to the {0}."
            .format(utils.term('order')))

    def get_order_status(self, order):
        "Get the order status lookup item."
        return settings['ORDER_STATUSES_LOOKUP'][order['status']]

    def get_targets(self, order, check_valid=True):
        "Get the allowed status transition targets."
        result = []
        for transition in settings['ORDER_TRANSITIONS']:
            if transition['source'] != order['status']: continue
            if check_valid and \
               transition.get('require') == 'valid' and order['invalid']:
                continue
            permission = transition['permission']
            if (self.is_admin() and constants.ADMIN in permission) or \
               (self.is_staff() and constants.STAFF in permission) or \
               (self.is_owner(order) and constants.USER in permission):
                result.extend(transition['targets'])
        targets = [settings['ORDER_STATUSES_LOOKUP'][t] for t in result]
        if not self.global_modes['allow_order_submission']:
            targets = [t for t in targets
                       if t['identifier'] != constants.SUBMITTED]
        return targets

    def is_transitionable(self, order, status, check_valid=True):
        "Can the order be set to the given status?"
        targets = self.get_targets(order, check_valid=check_valid)
        return status in [t['identifier'] for t in targets]

    def check_transitionable(self, order, status, check_valid=True):
        "Check if the current user may set the order to the given status."
        if self.is_transitionable(order, status, check_valid=check_valid):
            return
        raise ValueError('You may not change status of {0} to {1}.'
                         .format(utils.term('order'), status))

    def is_submittable(self, order, check_valid=True):
        "Is the order submittable? Special hard-wired status."
        targets = self.get_targets(order, check_valid=check_valid)
        return constants.SUBMITTED in [t['identifier'] for t in targets]

    def is_clonable(self, order):
        """Can the given order be cloned? Its form must be enabled.
        Special case: Admin can clone an order even if its form is disabled.
        """
        form = self.get_entity(order['form'], doctype=constants.FORM)
        if self.is_admin():
            return form['status'] in (constants.ENABLED,
                                      constants.TESTING,
                                      constants.DISABLED)
        if not self.global_modes['allow_order_creation']: return False
        return form['status'] in (constants.ENABLED, constants.TESTING)


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
        form_titles = sorted(set([f[0] for f in self.get_forms()]))
        self.render('orders.html',
                    form_titles=form_titles,
                    order_column=order_column,
                    params=self.get_filter_params())

    def get_filter_params(self):
        "Return a dictionary with the filter parameters."
        result = dict()
        for key in ['status', 'form_title'] + \
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


class OrderApiV1Mixin:
    "Generate JSON for an order; both for orders list and order API."

    def get_json(self, order, names={}, forms={}, item=None):
        URL = self.absolute_reverse_url
        if not item:
            item = OD()
        item['iuid'] = order['_id']
        item['identifier'] = order.get('identifier')
        item['name'] = order.get('identifier') or order['_id'][:6] + '...'
        item['title'] = order.get('title') or '[no title]'
        item['form'] = dict(
            iuid=order['form'],
            title=forms.get(order['form']),
            links=dict(api=dict(href=URL('form_api', order['form'])),
                       display=dict(href=URL('form', order['form']))))
        item['owner'] = dict(
            email=order['owner'],
            name=names.get(order['owner']),
            links=dict(api=dict(href=URL('account_api', order['owner'])),
                       display=dict(href=URL('account', order['owner']))))
        item['fields'] = {}
        for f in settings['ORDERS_LIST_FIELDS']:
            item['fields'][f['identifier']] = order['fields'].get(f['identifier'])
        item['tags'] = order.get('tags', [])
        item['status'] = dict(
            name=order['status'],
            display=dict(href=URL('site', order['status']+'.png')))
        item['history'] = {}
        for s in settings['ORDERS_LIST_STATUSES']:
            item['history'][s] = order['history'].get(s)
        item['modified'] = order['modified']
        item['links'] = dict(
            self=dict(href=self.order_reverse_url(order, api=True)),
            display=dict(href=self.order_reverse_url(order)))
        return item


class OrdersApiV1(OrderApiV1Mixin, Orders):
    "Orders API; JSON output."

    @tornado.web.authenticated
    def get(self):
        "JSON output."
        URL = self.absolute_reverse_url
        self.check_staff()
        self.params = self.get_filter_params()
        # Get names and forms lookups
        names = self.get_account_names()
        forms = dict([(f[1], f[0]) for f in self.get_forms(all=True)])
        data = OD()
        data['type'] = 'orders'
        data['links'] = dict(self=dict(href=URL('orders_api')),
                             display=dict(href=URL('orders')))
        data['items'] = [self.get_json(o, names, forms)
                         for o in self.get_orders(forms)]
        self.write(data)

    def get_orders(self, forms):
        orders = self.filter_by_status(self.params.get('status'))
        orders = self.filter_by_forms(self.params.get('form_title'),
                                      forms=forms,
                                      orders=orders)
        for f in settings['ORDERS_LIST_FIELDS']:
            orders = self.filter_by_field(f['identifier'],
                                          self.params.get(f['identifier']),
                                          orders=orders)
        try:
            limit = settings['DISPLAY_ORDERS_MOST_RECENT']
            if not isinstance(limit, int): raise ValueError
        except (ValueError, KeyError):
            limit = 0
        # No filter; all orders
        if orders is None:
            if limit > 0 and self.params.get('recent', True):
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True,
                                    limit=limit)
            else:
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True)
            orders = [r.doc for r in view]
        elif limit > 0 and self.params.get('recent', True):
            orders = orders[:limit]
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

    def filter_by_forms(self, form_title, forms, orders=None):
        "Return orders list if any form filter, or None if none."
        if form_title:
            forms = set([f[0] for f in forms.items() if f[1] == form_title])
            if orders is None:
                orders = []
                for form in forms:
                    view = self.db.view('order/form',
                                        descending=True,
                                        reduce=False,
                                        include_docs=True)
                    orders.extend([r.doc for r in
                                   view[[form, constants.CEILING]:[form]]])
            else:
                orders = [o for o in orders if o['form'] in forms]
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
            try:
                order = self.get_entity(iuid, doctype=constants.ORDER)
            except tornado.web.HTTPError, msg:
                self.see_other('home', error=str(msg))
                return
        else:
            order = self.get_entity_view('order/identifier', match.group())
        try:
            self.check_readable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        form = self.get_entity(order['form'], doctype=constants.FORM)
        files = []
        for filename in order.get('_attachments', []):
            stub = order['_attachments'][filename]
            files.append(dict(filename=filename,
                              size=stub['length'],
                              content_type=stub['content_type']))
            files.sort(lambda i,j: cmp(i['filename'].lower(),
                                       j['filename'].lower()))
        self.render('order.html',
                    title=u"{0} '{1}'".format(utils.term('Order'),
                                              order['title']),
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
            405, reason='Internal problem; POST only allowed for DELETE.')

    @tornado.web.authenticated
    def delete(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.delete_logs(order['_id'])
        self.db.delete(order)
        self.see_other('orders')


class OrderApiV1(ApiV1Mixin, OrderApiV1Mixin, Order):
    "Order API; JSON."

    def render(self, templatefilename, **kwargs):
        order = kwargs['order']
        data = OD()
        data['type'] = 'order'
        data = self.get_json(order,
                             names=self.get_account_names([order['owner']]),
                             item=data)
        data['fields'] = order['fields']
        data['files'] = []
        for filename in order.get('_attachments', []):
            stub = order['_attachments'][filename]
            data['files'].append(
                dict(filename=filename,
                     href=self.absolute_reverse_url('order_file',
                                                    order['_id'],
                                                    filename),
                     size=stub['length'],
                     content_type=stub['content_type']))
        data['invalid'] = order['invalid']
        self.write(data)


class OrderLogs(OrderMixin, RequestHandler):
    "Order log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.render('logs.html',
                    title=u"Logs for {0} '{1}'".format(utils.term('order'),
                                                       order['title']),
                    entity=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(RequestHandler):
    "Create a new order. Redirect with error message if not logged in."

    def get(self):
        if not self.current_user:
            self.see_other('home',
                           error="You need to be logged in to create {0}."
                           " Register to get an account if you don't have one."
                           .format(utils.term('order')))
            return
        if not self.global_modes['allow_order_creation'] \
           and self.current_user['role'] != constants.ADMIN:
            self.see_other('home',
                           error="{0} creation is currently disabled."
                           .format(utils.term('Order')))
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
            # First try to set the value of a field from the corresponding
            # value defined for the account's university.
            autopopulate = settings.get('ORDER_AUTOPOPULATE', {})
            uni_fields = settings['UNIVERSITIES'].\
                get(self.current_user.get('university'), {}).get('fields', {})
            for target in autopopulate:
                if target not in fields: continue
                value = uni_fields.get(target)
                # Terrible kludge! If it looks like a country field,
                # then translate from country code to name.
                if 'country' in target:
                    try:
                        value = settings['COUNTRIES_LOOKUP'][value]
                    except KeyError:
                        pass
                saver['fields'][target] = value
            # Next try to set the value of a field from the corresponding
            # value defined for the account. For use with e.g. invoice address.
            # Do this only if not done already from university data.
            for target, source in autopopulate.iteritems():
                if target not in fields: continue
                value = saver['fields'].get(target)
                if isinstance(value, basestring):
                    if value: continue
                elif value is not None: # Value 0 (zero) must be possible to set
                    continue
                try:
                    key1, key2 = source.split('.')
                except ValueError:
                    value = self.current_user.get(source)
                else:
                    value = self.current_user.get(key1, {}).get(key2)
                # Terrible kludge! If it looks like a country field,
                # then translate from country code to name.
                if 'country' in target:
                    try:
                        value = settings['COUNTRIES_LOOKUP'][value]
                    except KeyError:
                        pass
                saver['fields'][target] = value
            saver.check_fields_validity(fields)
            saver.set_identifier(form)
        self.see_other('order_edit', saver.doc['_id'])


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        colleagues = sorted(self.get_account_colleagues(self.current_user['email']))
        form = self.get_entity(order['form'], doctype=constants.FORM)
        fields = Fields(form)
        # XXX Currently, multiselect fields are not handled correctly.
        #     Too much effort; leave as is for the time being.
        hidden_fields = set([f['identifier'] for f in fields.flatten()
                             if f['type'] != 'multiselect'])
        self.render('order_edit.html',
                    title=u"Edit {0} '{1}'".format(utils.term('order'),
                                                   order['title']),
                    order=order,
                    colleagues=colleagues,
                    form=form,
                    fields=form['fields'],
                    hidden_fields=hidden_fields,
                    is_submittable=self.is_submittable(order,check_valid=False))

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        flag = self.get_argument('__save__', None)
        try:
            message = "{0} saved.".format(utils.term('Order'))
            error = None
            with OrderSaver(doc=order, rqh=self) as saver:
                saver['title'] = self.get_argument('__title__', None) or '[no title]'
                tags = []
                for tag in self.get_argument('__tags__', '').split(','):
                    tag = tag.strip()
                    if tag: tags.append(tag)
                # Allow staff to add prefixed tags
                if self.is_staff():
                    for pos, tag in enumerate(tags):
                        parts = tag.split(':', 1)
                        for part in parts:
                            if not constants.ID_RX.match(part):
                                tags[pos] = None
                    tags = [t for t in tags if t]
                # User may not use prefixes
                else:
                    tags = [t for t in tags if constants.ID_RX.match(t)]
                    # Add back the previously defined prefixed tags
                    tags.extend([t for t in order.get('tags', [])
                                 if ':' in t])
                saver['tags'] = sorted(set(tags))
                try:
                    owner = self.get_argument('__owner__')
                    account = self.get_account(owner)
                    if account.get('status') != constants.ENABLED:
                        raise ValueError('Owner account is not enabled.')
                except tornado.web.MissingArgumentError:
                    pass
                except tornado.web.HTTPError:
                    raise ValueError('Sorry, no such owner account.')
                else:
                    saver['owner'] = account['email']
                saver.update_fields()
                if flag == constants.SUBMIT: # Hard-wired status
                    if self.is_submittable(saver.doc):
                        saver.set_status(constants.SUBMITTED)
                        message = "{0} saved and submitted."\
                            .format(utils.term('Order'))
                    else:
                        error = "{0} could not be submitted due to" \
                                " invalid or missing values."\
                                .format(utils.term('Order'))
            if flag == 'continue':
                self.see_other('order_edit', order['_id'], message=message)
            else:
                if error:
                    url = self.order_reverse_url(order,
                                                 message=message,
                                                 error=error)
                else:
                    url = self.order_reverse_url(order, message=message)
                self.redirect(url)
        except ValueError, msg:
            self.redirect(self.order_reverse_url(order, error=str(msg)))


class OrderClone(OrderMixin, RequestHandler):
    "Create a new order from an existing one."

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        if not self.is_clonable(order):
            raise ValueError("This {0} is outdated; its form has been disabled."
                             .format(utils.term('order')))
        form = self.get_entity(order['form'], doctype=constants.FORM)
        fields = Fields(form)
        erased_files = set()
        with OrderSaver(rqh=self) as saver:
            saver['form'] = form['_id']
            saver['title'] = u"Clone of {0}".format(order['title'])
            saver['fields'] = dict()
            for field in fields:
                id = field['identifier']
                if field.get('erase_on_clone'):
                    if field['type'] == constants.FILE:
                        erased_files.add(order['fields'][id])
                    saver['fields'][id] = None
                else:
                    saver['fields'][id] = order['fields'][id]
            saver['history'] = {}
            saver.set_status(settings['ORDER_STATUS_INITIAL']['identifier'])
            saver.check_fields_validity(fields)
            saver.set_identifier(form)
        for filename in order.get('_attachments', []):
            if filename in erased_files: continue
            stub = order['_attachments'][filename]
            outfile = self.db.get_attachment(order, filename)
            self.db.put_attachment(saver.doc,
                                   outfile,
                                   filename=filename,
                                   content_type=stub['content_type'])
        self.redirect(self.order_reverse_url(saver.doc))


class OrderTransition(OrderMixin, RequestHandler):
    "Change the status of an order."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_transitionable(order, targetid)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.set_status(targetid)
        self.redirect(self.order_reverse_url(order))


class OrderTransitionApiV1(OrderMixin, RequestHandler):
    "Change the status of an order by an API call."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_transitionable(order, targetid)
        except ValueError, msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        with OrderSaver(doc=order, rqh=self) as saver:
            saver.set_status(targetid)
        self.redirect(self.order_reverse_url(order, api=True))

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when script is calling."
        pass


class OrderFile(OrderMixin, RequestHandler):
    "File attached to an order."

    @tornado.web.authenticated
    def get(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        outfile = self.db.get_attachment(order, filename)
        if outfile is None:
            self.see_other('order', iuid, error='No such file.')
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
            405, reason='Internal problem; POST only allowed for DELETE.')

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        fields = Fields(self.get_entity(order['form'], doctype=constants.FORM))
        with OrderSaver(doc=order, rqh=self) as saver:
            docfields = order['fields']
            for key in docfields:
                # Remove the field value if it is the filename.
                # XXX Slightly dangerous: may delete a value that happens to
                # be identical to the filename. Shouldn't be too commmon...
                if docfields[key] == filename:
                    docfields[key] = None
                    if fields[key]['required']:
                        saver.doc['invalid'][key] = 'missing value'
                    else:
                        try:
                            del saver.doc['invalid'][key]
                        except KeyError:
                            pass
                    break
            saver.delete_filename = filename
            saver.changed['file_deleted'] = filename
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
                saver.add_file(infile)
        self.redirect(self.order_reverse_url(order))
