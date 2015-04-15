"OrderPortal: Form pages."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.requesthandler import RequestHandler


class FormSaver(saver.Saver):
    doctype = constants.FORM


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
        self.check_admin()
        self.check_xsrf_cookie()
        with FormSaver(rqh=self) as saver:
            saver['title'] = self.get_argument('title')
            saver['fields'] = []
            saver['status'] = constants.PENDING
            saver['owner'] = self.current_user['email']
            doc = saver.doc
        self.see_other(self.reverse_url('form_edit', doc['_id']))


class FormEdit(RequestHandler):
    "Page for editing an form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render('form_edit.html',
                    title="Edit form '{}'".format(form['title']),
                    form=form)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        self.check_xsrf_cookie()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver.update_fields()
        self.see_other(self.reverse_url('form', form['_id']))
