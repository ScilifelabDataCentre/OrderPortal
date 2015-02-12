"OrderPortal: Field page."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.requesthandler import RequestHandler


class FieldSaver(saver.Saver):
    doctype = constants.FIELD


class Fields(RequestHandler):
    "Fields list page."

    def get(self):
        fields = self.get_all_fields_flattened()
        self.render('fields.html', title='Fields', fields=fields)


class Field(RequestHandler):
    "Field page."

    def get(self, identifier):
        field = self.get_field(identifier)
        self.render('field.html',
                    title="Field '{}'".format(field['identifier']),
                    field=field,
                    logs=self.get_logs(field['_id']))


class FieldCreate(RequestHandler):
    "Page for creating a field."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('field_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        self.check_xsrf_cookie()
        identifier = self.get_argument('identifier')
        if not constants.ID_RX.match(identifier):
            raise tornado.web.HTTPError(400, reason='invalid identifier')
        try:
            field = self.get_field(identifier)
        except tornado.web.HTTPError:
            pass
        else:
            raise tornado.web.HTTPError(400, reason='non-unique identifier')
        type = self.get_argument('type')
        if type not in constants.TYPES_SET:
            raise tornado.web.HTTPError(400, reason='invalid type')
        with FieldSaver(rqh=self) as saver:
            saver['identifier'] = identifier
            saver['type'] = type
            saver.save_required()
            saver['label'] = self.get_argument('label', None)
            saver['parent'] = None
            try:
                saver['position'] = int(self.get_argument('position', 0))
            except ValueError:
                saver['position'] = 0
            saver['description'] = self.get_argument('description', None)
        self.see_other(self.reverse_url('field', identifier))


class FieldEdit(RequestHandler):
    "Field edit page."

    @tornado.web.authenticated
    def get(self, identifier):
        self.check_admin()
        field = self.get_field(identifier)
        fields = self.get_all_fields_flattened(exclude=field)
        self.render('field_edit.html', field=field, fields=fields)

    @tornado.web.authenticated
    def post(self, identifier):
        self.check_admin()
        self.check_xsrf_cookie()
        field = self.get_field(identifier)
        with FieldSaver(doc=field, rqh=self) as saver:
            saver.save_required()
            saver['label'] = self.get_argument('label', None)
            if field['type'] == 'select':
                items = self.get_argument('options', '').split('\n')
                items = [i.strip() for i in items]
                saver['options'] = [i for i in items if i]
            parent = self.get_argument('parent', None)
            if parent == '__top__':
                saver['parent'] = None
            elif parent:
                try:
                    parent = self.get_field(parent)
                except tornado.web.HTTPError:
                    pass
                else:
                    f = parent
                    while True:
                        if f['parent'] is None: break
                        if f['parent'] == field['identifier']:
                            raise tornado.web.HTTPError(
                                400, reason='parent is beneath this field')
                        f = self.get_field(f['parent'])
                    saver['parent'] = parent['identifier']
            try:
                saver['position'] = int(self.get_argument('position', 0))
            except ValueError:
                saver['position'] = 0
            saver['description'] = self.get_argument('description', None)
        self.see_other(self.reverse_url('field', identifier))
