"OrderPortal: Form pages."

from __future__ import print_function, absolute_import

import json
import logging

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

    def setup(self):
        self.fields = Fields(self.doc)

    def add_field(self):
        identifier = self.rqh.get_argument('identifier')
        if not constants.ID_RX.match(identifier):
            raise tornado.web.HTTPError(400, reason='invalid identifier')
        if self.rqh.get_argument('type') not in constants.TYPES:
            raise tornado.web.HTTPError(400, reason='invalid type')
        if identifier in self.fields:
            raise tornado.web.HTTPError(409, reason='identifier already exists')
        self.changed['fields'] = self.fields.add(identifier, self.rqh)

    def update_field(self, identifier):
        if identifier not in self.fields:
            raise tornado.web.HTTPError(404, reason='no such field')
        self.changed['fields'] = self.fields.update(identifier, self.rqh)

    def clone_fields(self, form):
        "Clone all fields from the given form."
        for field in form['fields']:
            self.fields.clone(field)
        self.changed['copied'] = u"from {0}".format(form['_id'])

    def delete_field(self, identifier):
        if identifier not in self.fields:
            raise tornado.web.HTTPError(404, reason='no such field')
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
            raise tornado.web.HTTPError(409, reason='form is not editable')

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
        self.check_xsrf_cookie()
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if not self.is_deletable(form):
            raise tornado.web.HTTPError(400, reason='form cannot be deleted')
        self.delete_logs(form['_id'])
        self.db.delete(form)
        self.see_other('forms')

    def is_deletable(self, form):
        "Can the form be deleted?."
        if form['status'] == constants.PENDING: return True
        if form['status'] == constants.ENABLED: return False
        if self.get_order_count(form) == 0: return True
        return False


class ApiV1Form(ApiV1Mixin, Form):
    "Form API; JSON."

    def render(self, filename, form, order_count, fields,
               is_deletable, are_fields_editable, logs):
        self.cleanup(form)
        self.write(form)


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
    "Page for creating an form."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('form_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.check_admin()
        with FormSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            if not saver['title']:
                raise tornado.web.HTTPError(400, reason='no title given')
            saver['description'] = self.get_argument('description', None)
            saver['status'] = constants.PENDING
            try:
                infile = self.request.files['import'][0]
                data = json.loads(infile.body)
                assert data[constants.DOCTYPE] == constants.FORM, 'doc must be form'
                if not saver['description']:
                    saver['description'] = data['description']
                saver['fields'] = data['fields']
            except Exception, msg:
                logging.info("Error importing form: %s", msg)
        self.see_other('form', saver.doc['_id'])


class FormEdit(FormMixin, RequestHandler):
    "Page for editing an form; title and description."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form_edit.html',
                    title=u"Edit form '{0}'".format(form['title']),
                    form=form)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['description'] = self.get_argument('description')
        self.see_other('form', form['_id'])


class FormFieldCreate(FormMixin, RequestHandler):
    "Page for creating a field in a form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_fields_editable(form)
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
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_fields_editable(form)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.add_field()
        self.see_other('form', form['_id'])


class FormFieldEdit(FormMixin, RequestHandler):
    "Page for editing or deleting a field in a form."

    @tornado.web.authenticated
    def get(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_fields_editable(form)
        fields = Fields(form)
        try:
            field = fields[identifier]
        except KeyError:
            raise tornado.web.HTTPError(404, reason='no such field')
        self.render('field_edit.html', form=form, field=field, fields=fields)

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, identifier)
            return
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_fields_editable(form)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.update_field(identifier)
        self.see_other('form', form['_id'])

    @tornado.web.authenticated
    def delete(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_fields_editable(form)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.delete_field(identifier)
        self.see_other('form', form['_id'])


class FormFieldEditDescr(FormMixin, RequestHandler):
    """Edit the label and description of a form field.
    This is allowed also for enabled forms."""

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.fields[identifier]['label'] = \
                self.get_argument("{0}/label".format(identifier), '')
            saver.fields[identifier]['description'] = \
                self.get_argument("{0}/descr".format(identifier), '')
        self.see_other('form', form['_id'])


class FormClone(RequestHandler):
    "Make a clone of a form."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(rqh=self) as saver:
            saver['title'] = u"Clone of {0}".format(form['title'])
            saver['description'] = form.get('description')
            saver.clone_fields(form)
            saver['status'] = constants.PENDING
        self.see_other('form_edit', saver.doc['_id'])


class FormPending(RequestHandler):
    """Change status from testing to pending.
    To allow editing after testing.
    All test orders for this form are deleted."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
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
        self.check_xsrf_cookie()
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
        self.check_xsrf_cookie()
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
        self.check_xsrf_cookie()
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
