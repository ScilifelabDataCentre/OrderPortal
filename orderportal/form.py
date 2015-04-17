"OrderPortal: Form pages."

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


class FormSaver(saver.Saver):
    doctype = constants.FORM

    def add_field(self):
        identifier = self.rqh.get_argument('identifier')
        if not constants.ID_RX.match(identifier):
            raise tornado.web.HTTPError(400, reason='invalid identifier')
        fields = Fields(self.doc)
        if identifier in fields:
            raise tornado.web.HTTPError(409, reason='identifier already exists')
        self.changed['fields'] = fields.add(identifier, self.rqh)

    def set_status(self):
        new = self.rqh.get_argument('status')
        if new not in constants.FORM_STATUSES:
            raise tornado.web.HTTPError(400, reason='invalid status')
        if new == self.doc['status']: return
        if new not in constants.FORM_TRANSITIONS[self.doc['status']]:
            raise tornado.web.HTTPError(400, reason='invalid status transition')
        saver['status'] = new


class Forms(RequestHandler):
    "Forms list page."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        view = self.db.view('form/modified', include_docs=True)
        title = 'Recent forms'
        forms = [self.get_presentable(r.doc) for r in view]
        self.render('forms.html', title=title, forms=forms)


class Form(RequestHandler):
    "Form page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form.html',
                    title="Form '{}'".format(form['title']),
                    form=form,
                    fields=Fields(form),
                    logs=self.get_logs(form['_id']))


class FormCreate(RequestHandler):
    "Page for creating an form."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('form_create.html',
                    title='Create a new form')

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.check_admin()
        with FormSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['description'] = self.get_argument('description')
            saver['fields'] = []
            saver['status'] = constants.PENDING
            saver['owner'] = self.current_user['email']
            doc = saver.doc
        self.see_other(self.reverse_url('form_edit', doc['_id']))


class FormEdit(RequestHandler):
    "Page for editing an form."

    @tornado.web.authenticated
    def get(self, iuid):
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_edit_form(form)
        self.render('form_edit.html',
                    title="Edit form '{}'".format(form['title']),
                    form=form)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_edit_form(form)
        with FormSaver(doc=form, rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['description'] = self.get_argument('description')
        self.see_other(self.reverse_url('form', form['_id']))


class FormFieldCreate(RequestHandler):
    "Page for creating a field in a form."

    @tornado.web.authenticated
    def get(self, iuid):
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_edit_form(form)
        self.render('field_create.html',
                    title="Create field in form '{}'".format(form['title']),
                    form=form,
                    fields=Fields(form))

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_xsrf_cookie()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.check_edit_form(form)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.add_field()
        self.see_other(self.reverse_url('form', form['_id']))
