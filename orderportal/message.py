"Message to account user; optionally by email."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import saver
from orderportal import settings


class MessageSaver(saver.Saver):
    doctype = constants.MESSAGE

    def initialize(self):
        super(MessageSaver, self).initialize()
        self['sender'] = settings['MESSAGE_SENDER_EMAIL']
        self.doc['sent'] = None

    def set_params(self, **kwargs):
        "Set the parameters to use for the message text."
        self.params = dict(
            site=settings['SITE_NAME'],
            support=settings.get('SITE_SUPPORT_EMAIL', '[not defined]'))
        self.params.update(kwargs)

    def set_template(self, template):
        self['subject'] = unicode(template['subject']).format(**self.params)
        self['text'] = unicode(template['text']).format(**self.params)

    def log(self):
        "Do not create any log entry; the message is its own log."
        pass
