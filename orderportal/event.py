"OrderPortal: Events pages."

from __future__ import unicode_literals, print_function, absolute_import

import logging
import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler
from orderportal.saver import Saver


class Events(RequestHandler):
    "Edit page for events items."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('events.html', events=self.get_events())
