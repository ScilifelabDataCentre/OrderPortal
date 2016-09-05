"OrderPortal: Form pages."

from __future__ import print_function, absolute_import

import json
import logging
from collections import OrderedDict as OD

import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler, ApiV1Mixin


class FormSaver(saver.Saver):
    doctype = constants.FORM

    def initialize(self):
        super(FormSaver, self).initialize()
        self.doc['fields'] = []
        self.doc['ordinal'] = 0

    def setup(self):
        self.fields = Fields(self.doc)

    def add_field(self):
        identifier = self.rqh.get_argument('identifier')
        if not constants.ID_RX.match(identifier):
            raise ValueError('Invalid identifier.')
        if self.rqh.get_argument('type') not in constants.TYPES:
            raise ValueError('Invalid type.')
        if identifier in self.fields:
            raise ValueError('Identifier already exists.')
        self.changed['fields'] = self.fields.add(identifier, self.rqh)

    def update_field(self, identifier):
        if identifier not in self.fields:
            raise ValueError('No such field.')
        self.changed['fields'] = self.fields.update(identifier, self.rqh)

    def clone_fields(self, form):
        "Clone all fields from the given form."
        for field in form['fields']:
            self.fields.clone(field)
        self.changed['copied'] = u"from {0}".format(form['_id'])

    def delete_field(self, identifier):
        if identifier not in self.fields:
            raise ValueError('No such field.')
        self.fields.delete(identifier)
        self.changed['fields'] = dict(identifier=identifier, action='deleted')


class FormMixin(object):
    "Mixin providing various methods."

    def are_fields_editable(self, form):
        "Are the form fields editable? Checks status only."
        return form['status'] == constants.PENDING

    def check_fields_editable(self, form):
        "Check if the form fields can be edited. Checks status only."
        if not self.are_fields_editable(form):
            raise ValueError('Form is not editable.')

    def get_order_count(self, form):
        "Return number of orders for the form."
        view = self.db.view('order/form',
                            startkey=[form['_id']],
                            endkey=[form['_id'], constants.CEILING])
        try:
            return list(view)[0].value
        except (TypeError, IndexError):
            return 0


class Forms(FormMixin, RequestHandler):
    "Forms list page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('form/modified', descending=True, include_docs=True)
        title = 'Recent forms'
        forms = [r.doc for r in view]
        names = self.get_account_names([f['owner'] for f in forms])
        counts = dict([(f['_id'], self.get_order_count(f))
                       for f in forms])
        self.render('forms.html',
                    title=title,
                    forms=forms,
                    account_names=names,
                    order_counts=counts)


class Form(FormMixin, RequestHandler):
    "Form page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form.html',
                    form=form,
                    order_count=self.get_order_count(form),
                    fields=Fields(form),
                    is_deletable=self.is_deletable(form),
                    are_fields_editable=self.are_fields_editable(form),
                    logs=self.get_logs(form['_id']))

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(
            405, reason='internal problem; POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if not self.is_deletable(form):
            self.see_other('form', form['_id'],
                           error='Form cannot be deleted.')
            return
        self.delete_logs(form['_id'])
        self.db.delete(form)
        self.see_other('forms')

    def is_deletable(self, form):
        "Can the form be deleted?."
        if form['status'] == constants.PENDING: return True
        if form['status'] == constants.ENABLED: return False
        if self.get_order_count(form) == 0: return True
        return False


class FormApiV1(ApiV1Mixin, Form):
    "Form API; JSON."

    def render(self, templatefilename, **kwargs):
        form = kwargs['form']
        data = OD()
        data['base'] = self.absolute_reverse_url('home')
        data['type'] = 'form'
        data['iuid'] = form['_id']
        data['title'] = form.get('title')
        data['version'] = form.get('version')
        data['description'] = form.get('description')
        data['owner'] = dict(
            email=form['owner'],
            links=dict(api=dict(
                    href=self.reverse_url('account_api', form['owner'])),
                       display=dict(
                    href=self.reverse_url('account', form['owner']))))
        data['status'] = form['status']
        data['modified'] = form['modified']
        data['created'] = form['created']
        data['links'] = dict(
            self=dict(href=self.reverse_url('form_api', form['_id'])),
            display=dict(href=self.reverse_url('form', form['_id'])))
        data['orders'] = dict(
            count=self.get_order_count(form),
            # XXX Added API href when available.
            display=dict(href=self.reverse_url('form_orders', form['_id'])))
        data['fields'] = form['fields']
        self.write(data)


class FormLogs(RequestHandler):
    "Form log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('logs.html',
                    title=u"Logs for form'{0}'".format(form['title']),
                    entity=form,
                    logs=self.get_logs(form['_id']))


class FormCreate(RequestHandler):
    "Page for creating an form. Allows for importing fields from form JSON."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('form_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        with FormSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            if not saver['title']:
                self.see_other('forms', error='No title given.')
                return
            saver['description'] = self.get_argument('description', None)
            saver['version'] = self.get_argument('version', None)
            saver['status'] = constants.PENDING
            try:
                infile = self.request.files['import'][0]
                # This throws exceptions if not JSON
                data = json.loads(infile.body)
                if data.get(constants.DOCTYPE) != constants.FORM and \
                   data.get('type') != 'form':
                    raise ValueError('imported JSON is not a form')
            except (KeyError, IndexError):
                pass
            except Exception, msg:
                self.see_other('home', error="Error importing form: %s" % msg)
                return
            else:
                if not saver['description']:
                    saver['description'] = data.get('description')
                if not saver['version']:
                    saver['version'] = data.get('version')
                saver['fields'] = data['fields']
        self.see_other('form', saver.doc['_id'])


class FormEdit(FormMixin, RequestHandler):
    "Page for editing an form; title, description, version."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form_edit.html',
                    title=u"Edit form '{0}'".format(form['title']),
                    form=form)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['description'] = self.get_argument('description', None)
            saver['version'] = self.get_argument('version', None)
            try:
                saver['ordinal'] = int(self.get_argument('ordinal', 0))
            except (ValueError, TypeError):
                pass
        self.see_other('form', form['_id'])


class FormFieldCreate(FormMixin, RequestHandler):
    "Page for creating a field in a form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_fields_editable(form)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
            return
        # Get existing field identifiers
        identifiers = set()
        for row in self.db.view('form/enabled', include_docs=True):
            identifiers.update(self._get_identifiers(row.doc['fields']))
        identifiers.difference_update(self._get_identifiers(form['fields']))
        self.render('field_create.html',
                    title=u"Create field in form '{0}'".format(form['title']),
                    form=form,
                    fields=Fields(form),
                    identifiers=identifiers)

    def _get_identifiers(self, fields):
        result = set()
        for field in fields:
            result.add(field['identifier'])
            try:
                result.update(self._get_identifiers(field['fields']))
            except KeyError:
                pass
        return result

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_fields_editable(form)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.add_field()
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
        else:
            self.see_other('form', form['_id'])


class FormFieldEdit(FormMixin, RequestHandler):
    "Page for editing or deleting a field in a form."

    @tornado.web.authenticated
    def get(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_fields_editable(form)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
            return
        fields = Fields(form)
        try:
            field = fields[identifier]
        except KeyError:
            self.see_other('form', form['_id'], error='No such field.')
            return
        self.render('field_edit.html',
                    form=form,
                    field=field,
                    fields=fields,
                    siblings=fields.get_siblings(field, form['fields']),
                    alt_parents=fields.get_alt_parents(field))

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, identifier)
            return
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_fields_editable(form)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.update_field(identifier)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
        else:
            self.see_other('form', form['_id'])

    @tornado.web.authenticated
    def delete(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_fields_editable(form)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.delete_field(identifier)
        except ValueError, msg:
            self.see_other('form', form['_id'], error=str(msg))
        else:
            self.see_other('form', form['_id'])


class FormFieldEditDescr(FormMixin, RequestHandler):
    """Edit the label, clone erase, description of a form field.
    This is allowed also for enabled forms."""

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.fields[identifier]['label'] = \
                self.get_argument("{0}/label".format(identifier), '')
            saver.fields[identifier]['erase_on_clone'] = \
                utils.to_bool(
                    self.get_argument("{0}/erase_on_clone".format(identifier),
                                      False))
            saver.fields[identifier]['description'] = \
                self.get_argument("{0}/descr".format(identifier), '')
        self.see_other('form', form['_id'])


class FormClone(RequestHandler):
    "Make a clone of a form."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(rqh=self) as saver:
            saver['title'] = u"Clone of {0}".format(form['title'])
            saver['description'] = form.get('description')
            saver['version'] = form.get('version')
            saver.clone_fields(form)
            saver['status'] = constants.PENDING
        self.see_other('form_edit', saver.doc['_id'])


class FormPending(RequestHandler):
    """Change status from testing to pending.
    To allow editing after testing.
    All test orders for this form are deleted."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form['status'] != constants.TESTING:
            raise ValueError('form does not have status testing')
        with FormSaver(doc=form, rqh=self) as saver:
            saver['status'] = constants.PENDING
        view = self.db.view('order/form',
                            reduce=False,
                            startkey=[form['_id']],
                            endkey=[form['_id'], constants.CEILING])
        for row in view:
            self.delete_logs(row.id)
            del self.db[row.id]
        self.see_other('form', iuid)


class FormTesting(RequestHandler):
    """Change status from pending to testing.
    To allow testing making orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form['status'] != constants.PENDING:
            raise ValueError('form does not have status pending')
        with FormSaver(doc=form, rqh=self) as saver:
            saver['status'] = constants.TESTING
        self.see_other('form', iuid)


class FormEnable(RequestHandler):
    """Change status from pending to enabled.
    Allows users to make orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form['status'] == constants.PENDING:
            with FormSaver(doc=form, rqh=self) as saver:
                saver['status'] = constants.ENABLED
        self.see_other('form', iuid)


class FormDisable(RequestHandler):
    """Change status from enabled to disabled.
    Disable making orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form['status'] == constants.ENABLED:
            with FormSaver(doc=form, rqh=self) as saver:
                saver['status'] = constants.DISABLED
        self.see_other('form', iuid)


class FormOrders(RequestHandler):
    "Page for a list of all orders for a given form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_staff()
        form = self.get_entity(iuid, doctype=constants.FORM)
        view = self.db.view('order/form',
                            startkey=[iuid],
                            endkey=[iuid, constants.CEILING])
        page = self.get_page(view=view)
        view = self.db.view('order/form',
                            reduce=False,
                            include_docs=True,
                            descending=True,
                            startkey=[iuid, constants.CEILING],
                            endkey=[iuid],
                            skip=page['start'],
                            limit=page['size'])
        orders = [r.doc for r in view]
        account_names = self.get_account_names([o['owner'] for o in orders])
        self.render('form_orders.html',
                    form=form,
                    orders=orders,
                    account_names=account_names,
                    params=dict(),
                    page=page)
