"Context handler for saving an entity as a CouchDB document. "

import couchdb2
import tornado.web

from orderportal import constants
from orderportal import utils


class Saver:
    "Context manager saving the data for the document."

    doctype = None

    def __init__(self, doc=None, handler=None, db=None):
        assert self.doctype
        if handler is not None:
            self.handler = handler
            self.db = handler.db
        elif db is not None:
            self.handler = None
            self.db = db
        else:
            raise AttributeError("neither db nor handler given")
        self.doc = doc or dict()
        self.changed = dict()
        if "_id" in self.doc:
            assert self.doctype == self.doc[constants.DOCTYPE]
        else:
            self.doc[constants.DOCTYPE] = self.doctype
            self.doc["_id"] = utils.get_iuid()
            self.initialize()
        self.setup()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if type is not None:
            return False  # No exceptions handled here.
        self.finalize()
        try:
            self.db.put(self.doc)
        except couchdb2.RevisionError:
            raise IOError("document revision update conflict")
        self.post_process()
        self.log()

    def __setitem__(self, key, value):
        "Update the key/value pair."
        try:
            checker = getattr(self, "check_{0}".format(key))
        except AttributeError:
            pass
        else:
            checker(value)
        try:
            converter = getattr(self, "convert_{0}".format(key))
        except AttributeError:
            pass
        else:
            value = converter(value)
        try:
            if self.doc[key] == value:
                return
        except KeyError:
            pass
        self.doc[key] = value
        self.changed[key] = value

    def __getitem__(self, key):
        return self.doc[key]

    def __delitem__(self, key):
        try:
            self.doc.pop(key, None)
        except AttributeError:
            pass
        else:
            self.changed[key] == "__del__"

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def initialize(self):
        "Set the initial values for the new document."
        try:
            self.doc["owner"] = self.handler.current_user["email"]
        except (TypeError, AttributeError, KeyError):
            self.doc["owner"] = None
        self.doc["created"] = utils.timestamp()

    def setup(self):
        "Any additional setup. To be redefined."
        pass

    def finalize(self):
        "Perform any final modifications before saving the document."
        self.doc["modified"] = utils.timestamp()

    def post_process(self):
        "Perform any actions after having saved the document. To be redefined."
        pass

    def log(self):
        "Create a log entry for the change."
        utils.log(self.db, self.handler, self.doc, changed=self.changed)
