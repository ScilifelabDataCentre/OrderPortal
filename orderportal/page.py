"OrderPortal: Pages for viewing; simplest possible CMS using Markdown."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import markdown
import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler
from orderportal.saver import Saver


class PageSaver(Saver):
    doctype = constants.PAGE

class Page(RequestHandler):
    "Page view."

    def get(self, name):
        page = self.get_entity_view('page/name', name)
        content = markdown.markdown(page['markdown'], output_format='html5')
        self.render('page.html',
                    name=name,
                    title=page.get('title') or 'No title',
                    content=content)


class Pages(RequestHandler):
    "List of pages."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('page/name', include_docs=True)
        pages = [r.doc for r in view]
        self.render('pages.html', pages=pages)


class PageCreate(RequestHandler):
    "Create a new page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('page_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        name = self.get_argument('name')
        if not constants.NAME_RX.match(name):
            raise tornado.web.HTTPError(400, reason='invalid page name')
        try:
            self.get_entity_view('page/name', name)
        except tornado.web.HTTPError:
            pass
        else:
            raise tornado.web.HTTPError(400, reason='named page already exists')
        with PageSaver(rqh=self) as saver:
            saver['name'] = name
            saver['title'] = self.get_argument('title', None)
            saver['markdown'] = self.get_argument('markdown', '')
        self.see_other('page', name)


class PageEdit(RequestHandler):
    "Edit the page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('page_edit.html')
