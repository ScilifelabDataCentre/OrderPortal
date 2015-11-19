"""OrderPortal: Send messages to users about recent events from log records.
To be run as a cron job.
"""

from __future__ import print_function, absolute_import

import email.mime.text
import smtplib
import urllib

import couchdb
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
        if self.verbose:
            print('Messenger', utils.timestamp())
        try:
            with open(settings['ACCOUNT_MESSAGES_FILENAME']) as infile:
                self.account_messages = yaml.safe_load(infile)
        except (IOError, KeyError):
            self.account_messages = {}
        try:
            with open(settings['ORDER_MESSAGES_FILENAME']) as infile:
                self.order_messages = yaml.safe_load(infile)
        except (IOError, KeyError):
            self.order_messages = {}

    @property
    def server(self):
        try:
            return self._server
        except AttributeError:
            host = settings['EMAIL']['HOST']
            if self.verbose:
                print('host', host)
            try:
                port = settings['EMAIL']['PORT']
                if self.verbose:
                    print('port', port)
            except KeyError:
                self._server = smtplib.SMTP(host)
            else:
                self._server = smtplib.SMTP(host, port=port)
            if settings['EMAIL'].get('TLS'):
                self._server.starttls()
            try:
                user = settings['EMAIL']['USER']
                password = settings['EMAIL']['PASSWORD']
            except KeyError:
                pass
            else:
                self._server.login(user, password)
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
                            startkey=constants.CEILING,
                            endkey=endkey)
        for row in view:
            if self.verbose:
                print('log', row.id)
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
        message = self.account_messages.get('pending')
        if not message: return
        try:
            account = self.db[logdoc['entity']]
        except couchdb.ResourceNotFound:
            return
        params = dict(site=settings['SITE_NAME'],
                      account=account['email'],
                      url=self.absolute_url('account', account['email']))
        self.send_email(self.get_admins(), message, params)

    def process_account_enabled(self, logdoc):
        """Account was enabled. Send URL and code for setting password."""
        message = self.account_messages.get('enabled')
        if not message: return
        try:
            account = self.db[logdoc['entity']]
        except couchdb.ResourceNotFound:
            return
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
        status = logdoc['changed'].get('status')
        message = self.order_messages.get(status)
        if not message: return
        try:
            order = self.db[logdoc['entity']]
        except couchdb.ResourceNotFound:
            return
        owner = self.get_account(order['owner'])
        # Owner may have disappeared (OK, OK, unlikely)
        if not owner: return
        params = dict(site=settings['SITE_NAME'],
                      owner=owner['email'],
                      order=order.get('title') or order['_id'],
                      url=self.absolute_url('order', order['_id']))
        # Send to administrators, if so configured
        for role in message['recipients']:
            if role == 'admin':
                self.send_email(self.get_admins(), message, params)
                break
        # Send to owner and group, if so configured
        recipients = set()
        for role in message['recipients']:
            if role == 'owner':
                recipients.add(owner['email'])
            elif role == 'group':
                recipients.update(self.get_colleagues(owner['email']))
        self.send_email(list(recipients), message, params)

    def send_email(self, recipients, message, params):
        "Actually send the message as email; not if the dry_run flag is set."
        if not recipients: return
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
            self.server.sendmail(sender, recipients, mail.as_string())
            with MessageSaver(db=self.db) as saver:
                saver['sender'] = sender
                saver['recipients'] = recipients
                saver['subject'] = subject
                saver['text'] = text
                saver['type'] = 'email'
            if self.verbose:
                print("sent email '{0}' to {1}".format(subject,
                                                       ', '.join(recipients)))

    def get_account(self, email):
        "Get the account document for the email."
        view = self.db.view('account/email', include_docs=True)
        try:
            return [r.doc for r in view[email]][0]
        except IndexError:
            return None

    def get_admins(self):
        "Get the list of enabled admin emails."
        view = self.db.view('account/role', include_docs=True)
        admins = [r.doc for r in view[constants.ADMIN]]
        return [a['email'] for a in admins if a['status'] == constants.ENABLED]

    def get_colleagues(self, email):
        "Get list of emails for accounts in same groups as the given email."
        colleagues = set()
        for row in self.db.view('group/member', include_docs=True, key=email):
            for member in row.doc['members']:
                account = self.get_account(member)
                if account['status'] == constants.ENABLED:
                    colleagues.add(account['email'])
        return list(colleagues)


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
