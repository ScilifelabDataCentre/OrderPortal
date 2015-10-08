"OrderPortal: Notify users about recent events. To be run as a cron job."

from __future__ import print_function, absolute_import

import email.mime.text
import smtplib
import urllib

import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.message import MessageSaver


class Notifier(object):
    "Process events and send messages for a subset of them."

    def __init__(self, db, verbose=False, dry_run=False):
        self.db = db
        self.verbose = verbose
        self.dry_run = dry_run
        try:
            with open(settings['ACCOUNT_MESSAGES_FILENAME']) as infile:
                self.account_messages = yaml.safe_load(infile)
        except (IOError, KeyError):
            self.account_messages = {}

    @property
    def server(self):
        try:
            return self._server
        except AttributeError:
            self._server = smtplib.SMTP(host=settings['EMAIL']['HOST'],
                                        port=settings['EMAIL']['PORT'])
            if settings['EMAIL'].get('TLS'):
                self._server.starttls()
            try:
                self._server.login(settings['EMAIL']['USER'],
                                   settings['EMAIL']['PASSWORD'])
            except KeyError:
                pass
            return self._server

    def __del__(self):
        try:
            self._server.quit()
        except AttributeError:
            pass

    def absolute_url(self, *args, **query):
        path = '/'
        if args:
            path += '/'.join(args)
        if query:
            path += '?' + urllib.urlencode(query)
        return settings['BASE_URL'].rstrip('/') + path

    def process_events(self):
        "Go through log entries for unprocessed events to send messages about."
        view = self.db.view('message/modified', descending=True, limit=1)
        messages = list(view)
        try:
            endkey = messages[0].key
        except IndexError:
            endkey = None
        if self.verbose:
            print('latest message', endkey)
        view = self.db.view('log/modified',
                            include_docs=True,
                            descending=True,
                            startkey=constants.HIGH_CHAR,
                            endkey=endkey)
        for row in view:
            if row.value == constants.ACCOUNT:
                self.process_account_event(row.doc)
            elif row.value == constants.ORDER:
                self.process_order_event(row.doc)

    def process_account_event(self, logdoc):
        "Send message when some specific event has occurred for an account."
        message = None
        if logdoc['changed'].get('status') == constants.PENDING:
            self.process_account_pending(logdoc)
        # Account has been enabled.
        elif logdoc['changed'].get('status') == constants.ENABLED:
            self.process_account_enabled(logdoc)

    def process_account_pending(self, logdoc):
        "Account was created, is pending. Tell the admins to enable it."
        message = self.account_messages.get('account_pending')
        if not message: return
        entity = self.db[logdoc['entity']]
        params = dict(site=settings['SITE_NAME'],
                      account=entity['email'],
                      url=self.absolute_url('account', entity['email']))
        self.send_email(subject=message['subject'].format(**params),
                        text=message['text'].format(**params),
                        recipients=self.get_recipients(entity, message))

    def process_account_enabled(self, logdoc):
        """Account was enabled. Send URL and code for setting password."""
        message = self.account_messages.get('account_enabled')
        if not message: return
        entity = self.db[logdoc['entity']]
        params = dict(site=settings['SITE_NAME'],
                      account=entity['email'],
                      url=self.absolute_url('password',
                                            email=entity['email'],
                                            code=entity['code']),
                      code=entity['code'])
        self.send_email(subject=message['subject'].format(**params),
                        text=message['text'].format(**params),
                        recipients=self.get_recipients(entity, message))

    def process_order_event(self, logdoc):
        "Send message when some specific event has happened to an order."
        print('order', logdoc['changed'])

    def send_email(self, recipients, subject, text):
        "Actually send the message as email; not if the dry_run flag is set."
        sender = settings['MESSAGE_SENDER_EMAIL']
        mail = email.mime.text.MIMEText(text)
        mail['Subject'] = subject
        mail['From'] = sender
        for recipient in recipients:
            mail['To'] = recipient
            if self.dry_run:
                print(mail.as_string())
            else:
                self.server.sendmail(sender, [recipient], mail.as_string())
        if not self.dry_run:
            with MessageSaver(db=self.db) as saver:
                saver['sender'] = sender
                saver['recipients'] = recipients
                saver['subject'] = subject
                saver['text'] = text
                saver['type'] = 'email'

    def get_recipients(self, entity, message):
        "Get list of recipient emails according to message roles and entity."
        result = set()
        for role in message['recipients']:
            if role == 'owner':
                result.add(entity['owner'])
            elif role == 'admin':
                result.update(self.get_admins())
        return list(result)

    def get_admins(self):
        "Get the list of admin emails."
        return ['per.kraulis@scilifelab.se']


def get_args():
    parser = utils.get_command_line_parser(description=
        'Send messages for recent events.')
    parser.add_option('-d', '--dry-run',
                      action='store_true', dest='dry_run', default=False,
                      help='do not send messages; for debug')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    notifier = Notifier(utils.get_db(),
                        verbose=options.verbose,
                        dry_run=options.dry_run)
    notifier.process_events()
