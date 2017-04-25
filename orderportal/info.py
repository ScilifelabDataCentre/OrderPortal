"Information pages; simplest possible CMS using Markdown."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class InfoSaver(saver.Saver):
    doctype = constants.INFO


class Info(RequestHandler):
    "Information page."

    def get(self, name):
        info = self.get_entity_view('info/name', name)
        self.render('info.html', info=info)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(name)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, name):
        self.check_admin()
        info = self.get_entity_view('info/name', name)
        self.delete_logs(info['_id'])
        self.db.delete(info)
        self.see_other('infos')


class InfoLogs(RequestHandler):
    "Info log entries page."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        info = self.get_entity_view('info/name', name)
        self.render('logs.html',
                    title=u"Logs for info '{0}'".format(name),
                    entity=info,
                    logs=self.get_logs(info['_id']))


class Infos(RequestHandler):
    "List of information pages."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('info/menu', include_docs=True)
        menu_infos = [r.doc for r in view]
        view = self.db.view('info/name', include_docs=True)
        rest_infos = [r.doc for r in view if r.doc.get('menu') is None]
        self.render('infos.html', all_infos=menu_infos + rest_infos)


class InfoCreate(RequestHandler):
    "Create a new information page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('info_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        name = self.get_argument('name')
        if not constants.NAME_RX.match(name):
            self.see_other('info_create', error='invalid info name')
            return
        try:
            self.get_entity_view('info/name', name)
        except tornado.web.HTTPError:
            pass
        else:
            self.see_other('info_create', error='named info already exists')
            return
        with InfoSaver(rqh=self) as saver:
            saver['name'] = name
            saver['title'] = self.get_argument('title', None)
            try:
                saver['menu'] = int(self.get_argument('menu', None))
            except (ValueError, TypeError):
                saver['menu'] = None
            saver['text'] = self.get_argument('text', '')
        self.see_other('info', name)


class InfoEdit(RequestHandler):
    "Edit the information page."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        info = self.get_entity_view('info/name', name)
        self.render('info_edit.html', info=info)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        info = self.get_entity_view('info/name', name)
        with InfoSaver(doc=info, rqh=self) as saver:
            saver['title'] = self.get_argument('title', None)
            try:
                saver['menu'] = int(self.get_argument('menu', None))
            except (ValueError, TypeError):
                saver['menu'] = None
            saver['text'] = self.get_argument('text', '')
        self.see_other('info', name)
