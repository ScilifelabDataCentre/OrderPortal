"OrderPortal: Message classes and pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .requesthandler import RequestHandler


class MessageSaver(saver.Saver):
    doctype = constants.MESSAGE

    def log(self):
        "No log entry for message; its creation is a log in itself."
        pass
