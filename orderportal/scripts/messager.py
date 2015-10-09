"""OrderPortal: Send messages to users about recent events from log records.
To be run as a cron job.
"""

from __future__ import print_function, absolute_import

import email.mime.text
import smtplib
import urllib

import yaml

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils


class MessageSaver(saver.Saver):
    doctype = constants.MESSAGE

    def log(self):
        "No log entry for message; its creation is a log in itself."
        pass


class Messager(object):
    "Process log records and send messages for interesting events."

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

    def process_logs(self):
        "Go through unprocessed log entries for items to send messages about."
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
                self.process_account_log(row.doc)
            elif row.value == constants.ORDER:
                self.process_order_log(row.doc)

    def process_account_log(self, logdoc):
        "Send message for an interesting account log record."
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
        account = self.db[logdoc['entity']]
        params = dict(site=settings['SITE_NAME'],
                      account=account['email'],
                      url=self.absolute_url('account', account['email']))
        self.send_email(self.get_admins(), message, params)

    def process_account_enabled(self, logdoc):
        """Account was enabled. Send URL and code for setting password."""
        message = self.account_messages.get('account_enabled')
        if not message: return
        account = self.db[logdoc['entity']]
        params = dict(site=settings['SITE_NAME'],
                      account=account['email'],
                      url=self.absolute_url('password'),
                      url_code=self.absolute_url('password',
                                                 email=account['email'],
                                                 code=account['code']),
                      code=account['code'])
        self.send_email([account['owner']], message, params)

    def process_order_log(self, logdoc):
        "Send message for an interesting order log record."
        print('order', logdoc['changed'])

    def send_email(self, recipients, message, params):
        "Actually send the message as email; not if the dry_run flag is set."
        subject = message['subject'].format(**params)
        text = message['text'].format(**params)
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
                if self.verbose:
                    print("sent email '{}' to {}".format(subject, recipient))
        if not self.dry_run:
            with MessageSaver(db=self.db) as saver:
                saver['sender'] = sender
                saver['recipients'] = recipients
                saver['subject'] = subject
                saver['text'] = text
                saver['type'] = 'email'
        
    def get_admins(self):
        "Get the list of enabled admin emails."
        
        return ['per.kraulis@scilifelab.se']


def get_args():
    parser = utils.get_command_line_parser(description=
        'Send messages for recent log record events.')
    parser.add_option('-d', '--dry-run',
                      action='store_true', dest='dry_run', default=False,
                      help='do not send messages; for debug')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    messager = Messager(utils.get_db(),
                        verbose=options.verbose,
                        dry_run=options.dry_run)
    messager.process_logs()
