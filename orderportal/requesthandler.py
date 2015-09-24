"OrderPortal: RequestHandler subclass."

from __future__ import print_function, absolute_import

import collections
from email.mime.text import MIMEText
import json
import logging
import smtplib
import urllib

import couchdb
import tornado.web

import orderportal
from . import constants
from . import settings
from . import utils


class RequestHandler(tornado.web.RequestHandler):
    "Base request handler."

    def prepare(self):
        "Get the database connection."
        self.db = utils.get_db()

    def get_template_namespace(self):
        "Set the variables accessible within the template."
        result = super(RequestHandler, self).get_template_namespace()
        result['version'] = orderportal.__version__
        result['settings'] = settings
        result['constants'] = constants
        result['absolute_reverse_url'] = self.absolute_reverse_url
        result['is_staff'] = self.is_staff()
        result['is_admin'] = self.is_admin()
        result['error'] = self.get_argument('error', None)
        result['message'] = self.get_argument('message', None)
        result['infos'] = [r.value for r in self.db.view('info/menu')]
        result['files'] = [r.value for r in self.db.view('file/menu')]
        result['texts'] = [r.key for r in self.db.view('text/name')]
        return result

    def see_other(self, name, *args, **query):
        """Redirect to the absolute URL given by name
        using HTTP status 303 See Other."""
        url = self.absolute_reverse_url(name, *args, **query)
        self.redirect(url, status=303)

    def absolute_reverse_url(self, name, *args, **query):
        "Get the absolute URL given the handler name, arguments and query."
        if name is None:
            path = ''
        else:
            path = self.reverse_url(name, *args, **query)
        return settings['BASE_URL'].rstrip('/') + path

    def reverse_url(self, name, *args, **query):
        "Allow adding query arguments to the URL."
        url = super(RequestHandler, self).reverse_url(name, *args)
        url = url.rstrip('?')   # tornado bug? left-over '?' sometimes
        if query:
            url += '?' + urllib.urlencode(query)
        return url

    def get_current_user(self):
        """Get the currently logged-in user account, if any.
        This overrides a tornado function, otherwise it would have
        been called get_current_account."""
        email = self.get_secure_cookie(constants.USER_COOKIE)
        if not email:
            return None
        try:
            account = self.get_account(email)
        except tornado.web.HTTPError:
            return None
        # Check that account is enabled.
        if account.get('status') != constants.ENABLED:
            logging.debug("account %s not enabled", email)
            return None
        # Check if login session is invalidated.
        if account.get('login') is None:
            logging.debug("account %s has no login session", email)
            return None
        return account

    def is_owner(self, entity):
        "Does the current user own the given entity?"
        return self.current_user and \
            entity['owner'] == self.current_user['email']            

    def is_admin(self):
        "Is the current user admin?"
        # Not a property, since the above is not.
        return self.current_user and \
            self.current_user['role'] == constants.ADMIN

    def is_staff(self):
        "Is the current user staff or admin?"
        # Not a property, since the above is not.
        return self.current_user and \
            self.current_user['role'] in (constants.STAFF, constants.ADMIN)

    def check_admin(self):
        "Check if current user is admin."
        if not self.is_admin():
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'admin'")

    def check_staff(self):
        "Check if current user is staff or admin."
        if not self.is_staff():
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'staff'")

    def get_entity(self, iuid, doctype=None):
        """Get the entity by the IUID. Check the doctype, if given.
        Raise HTTP 404 if no such entity.
        """
        try:
            entity = self.db[iuid]
        except couchdb.ResourceNotFound:
            raise tornado.web.HTTPError(404, reason='no such entity')
        try:
            if doctype is not None and entity[constants.DOCTYPE] != doctype:
                raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(404, reason='invalid entity doctype')
        return entity

    def get_entity_view(self, viewname, key, reason='no such entity'):
        """Get the entity by the view name and the key.
        Raise HTTP 404 if no such entity.
        """
        view = self.db.view(viewname, include_docs=True)
        rows = list(view[key])
        if len(rows) == 1:
            return rows[0].doc
        else:
            raise tornado.web.HTTPError(404, reason=reason)

    def get_news(self):
        "Get all news items in descending 'modified' order."
        view = self.db.view('news/modified', include_docs=True, descending=True)
        return [r.doc for r in view]

    def get_events(self):
        "Get all events items in descending 'date' order."
        view = self.db.view('event/date', include_docs=True)
        return [r.doc for r in view]

    def get_entity_attachment_filename(self, entity):
        """Return the filename of the attachment for the given entity.
        Raise KeyError if no attachment.
        """
        return entity['_attachments'].keys()[0]

    def get_entity_attachment_data(self, entity):
        """Return the data of the attachment for the given entity.
        Return None if attachment has no data, or no attachment.
        """
        try:
            filename = self.get_entity_attachment_filename(entity)
        except KeyError:
            return None
        infile = self.db.get_attachment(entity, filename)
        if infile is None: # When file is empty
            data = None
        else:
            data = infile.read()
            infile.close()
        return data

    def get_account(self, email):
        """Get the account identified by the email address.
        Raise HTTP 404 if no such account.
        """
        return self.get_entity_view('account/email', email, reason='no such account')

    def get_account_groups(self, email):
        "Get sorted list of all groups which the account is a member of."
        view = self.db.view('group/member', include_docs=True)
        return sorted([r.doc for r in view[email]],
                      cmp=lambda i,j: cmp(i['name'], j['name']))

    def get_account_colleagues(self, email):
        """Return the set of all emails for colleagues of the account;
        members of groups which the account is a member of."""
        result = set()
        for group in self.get_account_groups(email):
            result.update(group['members'])
        return result

    def is_colleague(self, email):
        """Is the user with the given email address
        in the same group as the current user?"""
        if not self.current_user: return False
        return self.current_user['email'] in self.get_account_colleagues(email)

    def get_logs(self, iuid, limit=constants.DEFAULT_MAX_DISPLAY_LOG+1):
        "Return the event log documents for the given entity iuid."
        kwargs = dict(include_docs=True,
                      startkey=[iuid, constants.HIGH_CHAR],
                      endkey=[iuid],
                      descending=True)
        if limit > 0:
            kwargs['limit'] = limit
        view = self.db.view('log/entity', **kwargs)
        logs = [r.doc for r in view]
        # Ref to entity in DB is not needed in each log entry.
        for log in logs:
            log['iuid'] = log.pop('_id')
            log.pop('_rev')
            log.pop('orderportal_doctype')
            log.pop('entity')
        return logs

    def delete_logs(self, iuid):
        "Delete the event log documents for the given entity iuid."
        view = self.db.view('log/entity',
                            startkey=[iuid],
                            endkey=[iuid, constants.HIGH_CHAR])
        for row in view:
            del self.db[row.id]

    def send_email(self, recipient, subject, text, sender=None):
        "Send an email to the given recipient from the given sender account."
        if sender:
            from_address = sender['email']
        else:
            from_address = settings['EMAIL']['USER']
        mail = MIMEText(text)
        mail['Subject'] = subject
        mail['From'] = from_address
        mail['To'] = recipient
        server = smtplib.SMTP(host=settings['EMAIL']['HOST'],
                              port=settings['EMAIL']['PORT'])
        if settings['EMAIL'].get('TLS'):
            server.starttls()
        try:
            server.login(settings['EMAIL']['USER'],
                         settings['EMAIL']['PASSWORD'])
        except KeyError:
            pass
        logging.debug("sendmail to %s from %s", recipient, from_address)
        server.sendmail(from_address, [recipient], mail.as_string())
        server.quit()
