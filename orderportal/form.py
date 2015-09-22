"OrderPortal: Form pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler


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
        self.changed['copied'] = "from {}".format(form['_id'])

    def delete_field(self, identifier):
        if identifier not in self.fields:
            raise tornado.web.HTTPError(404, reason='no such field')
        self.fields.delete(identifier)
        self.changed['fields'] = dict(identifier=identifier, action='deleted')


class FormMixin(object):
    "Mixin providing form-related methods."

    def are_fields_editable(self, form):
        "Are the form fields editable? Checks status only."
        return form['status'] == constants.PENDING

    def check_fields_editable(self, form):
        "Check if the form fields can be edited. Checks status only."
        if not self.are_fields_editable(form):
            raise tornado.web.HTTPError(409, reason='form is not editable')


class Forms(RequestHandler):
    "Forms list page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('form/modified', descending=True, include_docs=True)
        title = 'Recent forms'
        forms = [r.doc for r in view]
        self.render('forms.html', title=title, forms=forms)


class Form(FormMixin, RequestHandler):
    "Form page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form.html',
                    form=form,
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
        return form['status'] == constants.PENDING


class FormLogs(RequestHandler):
    "Form log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('logs.html',
                    title="Logs for form'{}'".format(form['title']),
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
            saver['owner'] = self.current_user['email']
        self.see_other('form', saver.doc['_id'])


class FormEdit(FormMixin, RequestHandler):
    "Page for editing an form; title and description."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form_edit.html',
                    title="Edit form '{}'".format(form['title']),
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
        self.render('field_create.html',
                    title="Create field in form '{}'".format(form['title']),
                    form=form,
                    fields=Fields(form))

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
                self.get_argument("{}/label".format(identifier), '')
            saver.fields[identifier]['description'] = \
                self.get_argument("{}/descr".format(identifier), '')
        self.see_other('form', form['_id'])


class FormClone(RequestHandler):
    "Make a clone of a form."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(rqh=self) as saver:
            saver['title'] = "Clone of {}".format(form['title'])
            saver['description'] = form.get('description')
            saver.clone_fields(form)
            saver['status'] = constants.PENDING
            saver['owner'] = self.current_user['email']
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
        if form['status'] == constants.TESTING:
            with FormSaver(doc=form, rqh=self) as saver:
                saver['status'] = constants.PENDING
        view = self.db.view('order/form')
        for row in view[form['_id']]:
            self.delete_logs(row.id)
            del self.db[row.id]
        # XXX Delete all orders!
        self.see_other('form', iuid)


class FormTesting(RequestHandler):
    """Change status from pending to testing.
    To allow testing making orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form['status'] == constants.PENDING:
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
