"Account and login pages."

from __future__ import print_function, absolute_import

import csv
import logging
from collections import OrderedDict as OD
from cStringIO import StringIO

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.order import OrderApiV1Mixin
from orderportal.group import GroupSaver
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler


class AccountSaver(saver.Saver):
    doctype = constants.ACCOUNT

    def set_email(self, email):
        assert self.get('email') is None # Email must not have been set.
        email = email.strip().lower()
        if not email: raise ValueError('No email given.')
        if not constants.EMAIL_RX.match(email):
            raise ValueError('Malformed email value.')
        if len(list(self.db.view('account/email', key=email))) > 0:
            raise ValueError('Email is already in use.'
                             " Use 'Reset password' if you have lost it.")
        self['email'] = email

    def erase_password(self):
        self['password'] = None

    def set_password(self, new):
        utils.check_password(new)
        self['code'] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc['password'] = utils.hashed_password(new)
        self.changed['password'] = '******'

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self['code'] = utils.get_iuid()

    def check_required(self):
        "Check that required data is present. Raise ValueError otherwise."
        if not self['first_name']:
            raise ValueError('First name is required.')
        if not self['last_name']:
            raise ValueError('Last name is required.')
        if not self['university']:
            raise ValueError('University is required.')


class Accounts(RequestHandler):
    "Accounts list page."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        self.set_filter()
        self.render('accounts.html', 
                    accounts=self.get_accounts(),
                    filter=self.filter)

    def set_filter(self):
        "Set the filter parameters dictionary."
        self.filter = dict()
        for key in ['university', 'status', 'role']:
            try:
                value = self.get_argument(key)
                if not value: raise KeyError
                self.filter[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass

    def get_accounts(self):
        "Get the accounts."
        accounts = self.filter_by_university(self.filter.get('university'))
        accounts = self.filter_by_role(self.filter.get('role'),
                                       accounts=accounts)
        accounts = self.filter_by_status(self.filter.get('status'),
                                         accounts=accounts)
        # No filter; all accounts
        if accounts is None:
            view = self.db.view('account/email', include_docs=True)
            accounts = [r.doc for r in view]
        # This is optimized for retrieval speed. The single-valued
        # function 'get_account_order_count' is not good enough here.
        view = self.db.view('order/owner',
                            group_level=1,
                            startkey=[''],
                            endkey=[constants.CEILING])
        counts = dict([(r.key[0], r.value) for r in view])
        for account in accounts:
            account['order_count'] = counts.get(account['email'], 0)
            account['name'] = utils.get_account_name(account=account)
        return accounts

    def filter_by_university(self, university, accounts=None):
        "Return accounts list if any university filter, or None if none."
        if university == '[other]':
            if accounts is None:
                view = self.db.view('account/email', include_docs=True)
                accounts = [r.doc for r in view]
            accounts = [a for a in accounts
                        if a['university'] not in settings['UNIVERSITIES']]
        elif university:
            if accounts is None:
                view = self.db.view('account/university',
                                    key=university,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                account = [a for a in accounts
                           if a['university'] == university]
        return accounts

    def filter_by_role(self, role, accounts=None):
        "Return accounts list if any role filter, or None if none."
        if role:
            if accounts is None:
                view = self.db.view('account/role',
                                    key=role,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [a for a in accounts if a['role'] == role]
        return accounts

    def filter_by_status(self, status, accounts=None):
        "Return accounts list if any status filter, or None if none."
        if status:
            if accounts is None:
                view = self.db.view('account/status',
                                    key=status,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [a for a in accounts if a['status'] == status]
        return accounts


class AccountsApiV1(Accounts):
    "Accounts API; JSON output."

    @tornado.web.authenticated
    def get(self):
        "JSON output."
        URL = self.absolute_reverse_url
        self.check_staff()
        self.set_filter()
        accounts = self.get_accounts()
        data = utils.get_json(URL('accounts_api', **self.filter), 'accounts')
        data['filter'] = self.filter
        data['links'] = dict(api=dict(href=URL('accounts_api')),
                             display=dict(href=URL('accounts')))
        data['items'] = []
        for account in accounts:
            item = OD()
            item['email'] = account['email']
            item['links'] = dict(
                api=dict(href=URL('account_api',account['email'])),
                display=dict(href=URL('account',account['email'])))
            name = last_name = account.get('last_name')
            first_name = account.get('first_name')
            if name:
                if first_name:
                    name += ', ' + first_name
            else:
                name = first_name
            item['name'] = name
            item['first_name'] = first_name
            item['last_name'] = last_name
            item['pi'] = bool(account.get('pi'))
            item['gender'] = account.get('gender')
            item['university'] = account.get('university')
            item['role'] = account['role']
            item['status'] = account['status']
            item['address'] = account.get('address') or {}
            item['invoice_ref'] = account.get('invoice_ref')
            item['invoice_address'] = account.get('invoice_address') or {}
            item['login'] = account.get('login', '-')
            item['modified'] = account['modified']
            item['orders'] = dict(
                count=account['order_count'],
                links=dict(
                    display=dict(href=URL('account_orders', account['email'])),
                    api=dict(href=URL('account_orders_api', account['email']))))
            data['items'].append(item)
        self.write(data)


class AccountsCsv(Accounts):
    "Return a CSV file containing all data for all or filtered set of accounts."

    @tornado.web.authenticated
    def get(self):
        "CSV file output."
        self.check_staff()
        self.set_filter()
        accounts = self.get_accounts()
        csvfile = StringIO()
        writer = csv.writer(csvfile)
        writer.writerow((settings['SITE_NAME'], utils.timestamp()))
        writer.writerow(('Email', 'Last name', 'First name', 'Role', 'Status',
                         'Order count', 'University', 'Department', 'PI',
                         'Gender', 'Group size', 'Subject', 'Address', 'Zip',
                         'City', 'Country', 'Invoice ref', 'Invoice address',
                         'Invoice zip', 'Invoice city', 'Invoice country',
                         'Phone', 'Other data', 'Latest login',
                         'Modified', 'Created'))
        for account in accounts:
            addr = account.get('address') or dict()
            iaddr = account.get('invoice_address') or dict()
            try:
                subject = "{0}: {1}".format(
                    account.get('subject'),
                    settings['subjects_lookup'][account.get('subject')])
            except KeyError:
                subject = ''
            writer.writerow((utils.to_utf8(account['email']),
                             utils.to_utf8(account.get('last_name') or ''),
                             utils.to_utf8(account.get('first_name') or ''),
                             account['role'],
                             account['status'],
                             account['order_count'],
                             utils.to_utf8(account.get('university') or ''),
                             utils.to_utf8(account.get('department') or ''),
                             account.get('pi') and 'yes' or 'no',
                             account.get('gender') or '',
                             account.get('group_size') or '',
                             subject,
                             utils.to_utf8(addr.get('address') or ''),
                             utils.to_utf8(addr.get('zip') or ''),
                             utils.to_utf8(addr.get('city') or ''),
                             utils.to_utf8(addr.get('country') or ''),
                             utils.to_utf8(account.get('invoice_ref') or ''),
                             utils.to_utf8(iaddr.get('address') or ''),
                             utils.to_utf8(iaddr.get('zip') or ''),
                             utils.to_utf8(iaddr.get('city') or ''),
                             utils.to_utf8(iaddr.get('country') or ''),
                             utils.to_utf8(account.get('phone') or ''),
                             utils.to_utf8(account.get('other_data') or ''),
                             utils.to_utf8(account.get('login') or ''),
                             utils.to_utf8(account.get('modified') or ''),
                             utils.to_utf8(account.get('created') or ''),
                             ))
        self.write(csvfile.getvalue())
        self.set_header('Content-Type', constants.CSV_MIME)
        self.set_header('Content-Disposition',
                        'attachment; filename="accounts.csv"')


class AccountMixin(object):
    "Mixin for various useful methods."

    def is_readable(self, account):
        "Is the account readable by the current user?"
        if self.is_owner(account): return True
        if self.is_staff(): return True
        if self.is_colleague(account['email']): return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.is_readable(account): return
        raise ValueError('You may not read the account.')

    def is_editable(self, account):
        "Is the account editable by the current user?"
        if self.is_owner(account): return True
        if self.is_staff(): return True
        return False

    def check_editable(self, account):
        "Check that the account is editable by the current user."
        if self.is_readable(account): return
        raise ValueError('You may not edit the account.')


class Account(AccountMixin, RequestHandler):
    "Account page."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        account['order_count'] = self.get_account_order_count(account['email'])
        view = self.db.view('log/account',
                            startkey=[account['email'], constants.CEILING],
                            lastkey=[account['email']],
                            descending=True,
                            limit=1)
        try:
            key = list(view)[0].key
            if key[0] != account['email']: raise IndexError
            latest_activity = key[1]
        except IndexError:
            latest_activity = None
        if self.is_staff() or self.current_user['email'] == account['email']:
            invitations = self.get_invitations(account['email'])
        else:
            invitations = []
        self.render('account.html',
                    account=account,
                    groups=self.get_account_groups(account['email']),
                    latest_activity=latest_activity,
                    invitations=invitations,
                    is_deletable=self.is_deletable(account))

    @tornado.web.authenticated
    def post(self, email):
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(
            405, reason='Internal problem; POST only allowed for DELETE.')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a account that is pending; to get rid of spam application."
        account = self.get_account(email)
        self.check_admin()
        if not self.is_deletable(account):
            self.see_other('account', account['email'],
                           error='Account cannot be deleted.')
            return
        # Delete the groups this account owns.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=account['email'])
        for row in view:
            group = row.doc
            self.delete_logs(group['_id'])
            self.db.delete(group)
        # Remove this account from groups it is a member of.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=account['email'])
        for row in view:
            group = row.doc
            with GroupSaver(doc=row, rqh=self) as saver:
                members = set(group['members'])
                members.discard(account['email'])
                saver['members'] = sorted(members)
        # Delete the messages of the account.
        view = self.db.view('message/recipient',
                            reduce=False,
                            include_docs=True,
                            startkey=[account['email']],
                            endkey=[account['email'], constants.CEILING])
        for row in view:
            message = row.doc
            self.delete_logs(message['_id'])
            self.db.delete(message)
        # Delete the logs of the account.
        self.delete_logs(account['_id'])
        # Delete the account itself.
        self.db.delete(account)
        self.see_other('accounts')

    def is_deletable(self, account):
        "Can the account be deleted? Pending, or disabled and no orders."
        if account['status'] == constants.PENDING: return True
        if account['status'] == constants.ENABLED: return False
        if self.get_account_order_count(account['email']) == 0: return True
        return False


class AccountApiV1(AccountMixin, RequestHandler):
    "Account API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        data = utils.get_json(URL('account', email), 'account')
        data['email'] = account['email']
        name = last_name = account.get('last_name')
        first_name = account.get('first_name')
        if name:
            if first_name:
                name += ', ' + first_name
        else:
            name = first_name
        data['links'] = dict(
            api=dict(href=URL('account_api', account['email'])),
            display=dict(href=URL('account', account['email'])))
        data['name'] = name
        data['first_name'] = first_name
        data['last_name'] = last_name
        data['pi'] = bool(account.get('pi'))
        data['university'] = account['university']
        data['role'] = account['role']
        data['gender'] = account.get('gender')
        data['group_size'] = account.get('group_size')
        data['status'] = account['status']
        data['address'] = account.get('address') or {}
        data['invoice_ref'] = account.get('invoice_ref')
        data['invoice_address'] = account.get('invoice_address') or {}
        data['login'] = account.get('login', '-')
        data['modified'] = account['modified']
        view = self.db.view('log/account',
                            startkey=[account['email'], constants.CEILING],
                            lastkey=[account['email']],
                            descending=True,
                            limit=1)
        try:
            data['latest_activity'] = list(view)[0].key[1]
        except IndexError:
            data['latest_activity'] = None
        data['orders'] = dict(
            count=self.get_account_order_count(account['email']),
            display=dict(href=URL('account_orders', account['email'])),
            api=dict(href=URL('account_orders_api', account['email'])))
        self.write(data)


class AccountOrdersMixin(object):
    "Mixin containing access tests."

    def is_readable(self, account):
        "Is the account readable by the current user?"
        if account['email'] == self.current_user['email']: return True
        if self.is_staff(): return True
        if self.is_colleague(account['email']): return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.is_readable(account): return
        raise ValueError('You may not view these orders.')

    def get_group_orders(self, account):
        "Return all orders for the accounts in the account's group."
        orders = []
        for colleague in self.get_account_colleagues(account['email']):
            view = self.db.view('order/owner',
                                reduce=False,
                                include_docs=True,
                                startkey=[colleague],
                                endkey=[colleague, constants.CEILING])
            orders.extend([r.doc for r in view])
        return orders


class AccountOrders(AccountOrdersMixin, RequestHandler):
    "Page for a list of all orders for an account."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        if self.is_staff():
            order_column = 4
        else:
            order_column = 3
        order_column += len(settings['ORDERS_LIST_STATUSES']) + \
            len(settings['ORDERS_LIST_FIELDS'])
        view = self.db.view('order/owner',
                            reduce=False,
                            include_docs=True,
                            startkey=[account['email']],
                            endkey=[account['email'], constants.CEILING])
        orders = [r.doc for r in view]
        self.render('account_orders.html',
                    all_forms=self.get_forms_titles(all=True),
                    form_titles=sorted(self.get_forms_titles().values()),
                    orders=orders,
                    account=account,
                    order_column=order_column,
                    account_names=self.get_account_names(),
                    any_groups=bool(self.get_account_groups(account['email'])))


class AccountOrdersApiV1(AccountOrdersMixin,
                         OrderApiV1Mixin,
                         RequestHandler):
    "Account orders API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        "JSON output."
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        # Get names and forms lookups
        names = self.get_account_names()
        forms = self.get_forms_titles(all=True)
        data = utils.get_json(URL('account_orders', account['email']),
                              'account orders')
        data['links'] = dict(
            api=dict(href=URL('account_orders_api', account['email'])),
            display=dict(href=URL('account_orders', account['email'])))
        view = self.db.view('order/owner',
                            reduce=False,
                            include_docs=True,
                            startkey=[account['email']],
                            endkey=[account['email'], constants.CEILING])
        data['orders'] = [self.get_order_json(r.doc, names, forms)
                          for r in view]
        self.write(data)


class AccountGroupsOrders(AccountOrdersMixin, RequestHandler):
    "Page for a list of all orders for the groups of an account."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        if self.is_staff():
            order_column = 5
        else:
            order_column = 4
        order_column += len(settings['ORDERS_LIST_STATUSES']) + \
            len(settings['ORDERS_LIST_FIELDS'])
        self.render('account_groups_orders.html',
                    account=account,
                    all_forms=self.get_forms_titles(all=True),
                    orders=self.get_group_orders(account),
                    order_column=order_column)


class AccountGroupsOrdersApiV1(AccountOrdersMixin, 
                               OrderApiV1Mixin,
                               RequestHandler):
    "Account group orders API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        "JSON output."
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        # Get names and forms lookups
        names = self.get_account_names()
        forms = self.get_forms_titles(all=True)
        data =utils.get_json(URL('account_groups_orders_api',account['email']),
                             'account groups orders')
        data['links'] = dict(
            api=dict(href=URL('account_groups_orders_api', account['email'])),
            display=dict(href=URL('account_groups_orders', account['email'])))
        data['orders'] = [self.get_order_json(o, names, forms)
                          for o in self.get_group_orders(account)]
        self.write(data)


class AccountLogs(AccountMixin, RequestHandler):
    "Account log entries page."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.render('logs.html',
                    entity=account,
                    logs=self.get_logs(account['_id']))


class AccountMessages(AccountMixin, RequestHandler):
    "Account messages list page."

    @tornado.web.authenticated
    def get(self, email):
        "Show list of messages sent to the account given by email address."
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        view = self.db.view('message/recipient',
                            startkey=[account['email']],
                            endkey=[account['email'], constants.CEILING])
        view = self.db.view('message/recipient',
                            descending=True,
                            startkey=[account['email'], constants.CEILING],
                            endkey=[account['email']],
                            reduce=False,
                            include_docs=True)
        messages = [r.doc for r in view]
        self.render('account_messages.html',
                    account=account,
                    messages=messages)


class AccountEdit(AccountMixin, RequestHandler):
    "Page for editing account information."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_editable(account)
        except ValueError, msg:
            self.see_other('account', account['email'], error=str(msg))
            return
        self.render('account_edit.html', account=account)

    @tornado.web.authenticated
    def post(self, email):
        try:
            account = self.get_account(email)
            self.check_editable(account)
        except ValueError, msg:
            self.see_other('account_edit', account['email'], error=str(msg))
            return
        try:
            with AccountSaver(doc=account, rqh=self) as saver:
                # Only admin may change role of an account.
                if self.is_admin():
                    role = self.get_argument('role')
                    if role not in constants.ACCOUNT_ROLES:
                        raise ValueError('Invalid role.')
                    saver['role'] = role
                saver['first_name'] = self.get_argument('first_name')
                saver['last_name'] = self.get_argument('last_name')
                university = self.get_argument('university', None)
                if not university:
                    university = self.get_argument('university_other', None)
                saver['university'] = university
                saver['department'] = self.get_argument('department', None)
                saver['pi'] = utils.to_bool(self.get_argument('pi', False))
                try:
                    saver['gender'] = self.get_argument('gender').lower()
                except tornado.web.MissingArgumentError:
                    try:
                        del saver['gender']
                    except KeyError:
                        pass
                try:
                    saver['group_size'] = self.get_argument('group_size')
                except tornado.web.MissingArgumentError:
                    try:
                        del saver['group_size']
                    except KeyError:
                        pass
                try:
                    saver['subject'] = int(self.get_argument('subject'))
                except (tornado.web.MissingArgumentError, ValueError,TypeError):
                    saver['subject'] = None
                saver['address'] = dict(
                    address=self.get_argument('address', None),
                    zip=self.get_argument('zip', None),
                    city=self.get_argument('city', None),
                    country=self.get_argument('country', None))
                saver['invoice_ref'] = self.get_argument('invoice_ref', None)
                saver['invoice_address'] = dict(
                    address=self.get_argument('invoice_address', None),
                    zip=self.get_argument('invoice_zip', None),
                    city=self.get_argument('invoice_city', None),
                    country=self.get_argument('invoice_country', None))
                saver['phone'] = self.get_argument('phone', None)
                saver['other_data'] = self.get_argument('other_data', None)
                if utils.to_bool(self.get_argument('api_key', False)):
                    saver['api_key'] = utils.get_iuid()
                saver['update_info'] = False
                saver.check_required()
        except ValueError, msg:
            self.see_other('account_edit', account['email'], error=str(msg))
        else:
            self.see_other('account', account['email'])


class Login(RequestHandler):
    "Login to a account account. Set a secure cookie."

    def get(self):
        self.render('login.html', next=self.get_argument('next', None))

    def post(self):
        """Login to a account account. Set a secure cookie.
        Forward to account edit page if first login.
        Log failed login attempt. Disable account if too many recent.
        """
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
        except tornado.web.MissingArgumentError:
            self.see_other('home', error='Missing email or password argument.')
            return
        msg = 'Sorry, no such account or invalid password.'
        try:
            account = self.get_account(email)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        if utils.hashed_password(password) != account.get('password'):
            utils.log(self.db, self, account,
                      changed=dict(login_failure=account['email']))
            view = self.db.view('log/login_failure',
                                startkey=[account['_id'], utils.timestamp(-1)],
                                endkey=[account['_id'], utils.timestamp()])
            if len(list(view)) > settings['LOGIN_MAX_FAILURES']:
                logging.warning("account %s has been disabled due to"
                                " too many login failures", account['email'])
                with AccountSaver(doc=account, rqh=self) as saver:
                    saver['status'] = constants.DISABLED
                    saver.erase_password()
                msg = 'Too many failed login attempts: Your account has been' \
                      ' disabled. You must contact the site administrators.'
                # Prepare message sent by cron job script 'script/messenger.py'
                try:
                    template = settings['ACCOUNT_MESSAGES']['disabled']
                except KeyError:
                    pass
                else:
                    with MessageSaver(rqh=self) as saver:
                        saver.set_params()
                        saver.set_template(template)
                        saver['recipients'] = [account['email']]
            self.see_other('home', error=msg)
            return
        try:
            if not account.get('status') == constants.ENABLED:
                raise ValueError
        except ValueError:
            self.see_other('home', error='Account is disabled.'
                           ' Contact the site admin.')
            return
        if not self.global_modes['allow_login'] \
           and account['role'] != constants.ADMIN:
            self.see_other('home', error='Login is currently disabled.')
            return
        self.set_secure_cookie(constants.USER_COOKIE, account['email'],
                               expires_days=settings['LOGIN_MAX_AGE_DAYS'])
        with AccountSaver(doc=account, rqh=self) as saver:
            saver['login'] = utils.timestamp() # Set login timestamp.
        if account.get('update_info'):
            self.see_other('account_edit', account['email'],
                           message='Please review and update your account information.')
            return
        next = self.get_argument('next', None)
        if next is None:
            self.see_other('home')
        else:
            # Not quite right: should be an absolute URL to redirect.
            # But seems to work anyway.
            self.redirect(next)


class Logout(RequestHandler):
    "Logout; unset the secure cookie, and invalidate login session."

    @tornado.web.authenticated
    def post(self):
        self.set_secure_cookie(constants.USER_COOKIE, '')
        self.see_other('home')


class Reset(RequestHandler):
    "Reset the password of a account account."

    def get(self):
        self.render('reset.html', email=self.get_argument('account', ''))

    def post(self):
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(self.get_argument('email'))
        except (tornado.web.MissingArgumentError, ValueError):
            self.see_other('home') # Silent error! Should not show existence.
        else:
            if account.get('status') == constants.PENDING:
                self.see_other('home', error='Cannot reset password.'
                               ' Account has not been enabled.')
                return
            elif account.get('status') == constants.DISABLED:
                self.see_other('home', error='Cannot reset password.'
                               ' Account is disabled; contact the site admin.')
                return
            with AccountSaver(doc=account, rqh=self) as saver:
                saver.reset_password()
            # Prepare message sent by cron job script 'script/messenger.py'
            try:
                template = settings['ACCOUNT_MESSAGES']['reset']
            except KeyError:
                pass
            else:
                with MessageSaver(rqh=self) as saver:
                    saver.set_params(
                        account=account['email'],
                        url=URL('password'),
                        password_url=URL('password'),
                        password_code_url=URL('password',
                                              email=account['email'],
                                              code=account['code']),
                        code=account['code'])
                    saver.set_template(template)
                    saver['recipients'] = [account['email']]
            if self.current_user:
                if not self.is_admin():
                    # Log out the user
                    self.set_secure_cookie(constants.USER_COOKIE, '')
            self.see_other('home',
                           message="An email has been sent containing"
                           " a reset code. Please wait a couple of"
                           " minutes for it and use the link in it.")


class Password(RequestHandler):
    "Set the password of a account account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        try:
            account = self.get_account(self.get_argument('email', ''))
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        if account.get('code') != self.get_argument('code'):
            self.see_other('home',
                           error=
"""Either the email address or the code for setting password was wrong.
 You should probably request a new code using the 'Reset password' button.""")
            return
        password = self.get_argument('password', '')
        try:
            utils.check_password(password)
        except ValueError, msg:
            self.see_other('password',
                           email=self.get_argument('email') or '',
                           code=self.get_argument('code') or '',
                           error=str(msg))
            return 
        if password != self.get_argument('confirm_password'):
            self.see_other('password',
                           email=self.get_argument('email') or '',
                           code=self.get_argument('code') or '',
                           error='password confirmation failed. Not the same!')
            return
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, account['email'],
                               expires_days=settings['LOGIN_MAX_AGE_DAYS'])
        if account.get('update_info'):
            self.see_other('account_edit', account['email'],
                           message='Please review and update your account information.')
        else:
            self.see_other('home')


class Register(RequestHandler):
    "Register a new account account."

    KEYS = ['email', 'first_name', 'last_name',
            'university', 'department', 'pi',
            'gender', 'group_size', 'subject',
            'invoice_ref', 'phone']
    ADDRESS_KEYS = ['address', 'zip', 'city', 'country']

    def get(self):
        if not self.global_modes['allow_registration']:
            self.see_other('home', error='Registration is currently disabled.')
            return
        values = OD()
        for key in self.KEYS:
            values[key] = self.get_argument(key, None)
        for key in self.ADDRESS_KEYS:
            values[key] = self.get_argument(key, None)
        for key in self.ADDRESS_KEYS:
            values['invoice_' + key] = self.get_argument('invoice_' + key, None)
        self.render('register.html', values=values)

    def post(self):
        if not self.global_modes['allow_registration']:
            self.see_other('home', error='Registration is currently disabled.')
            return
        try:
            with AccountSaver(rqh=self) as saver:
                email = self.get_argument('email', None)
                saver['first_name'] = self.get_argument('first_name', None)
                saver['last_name'] = self.get_argument('last_name', None)
                university = self.get_argument('university', None)
                if not university:
                    university = self.get_argument('university_other', None)
                saver['university'] = university
                saver['department'] = self.get_argument('department', None)
                saver['pi'] = utils.to_bool(self.get_argument('pi', False))
                gender = self.get_argument('gender', None)
                if gender:
                    saver['gender'] = gender.lower()
                group_size = self.get_argument('group_size', None)
                if group_size:
                    saver['group_size'] = group_size
                try:
                    saver['subject'] = int(self.get_argument('subject'))
                except (tornado.web.MissingArgumentError,ValueError,TypeError):
                    saver['subject'] = None
                saver['address'] = dict(
                    address=self.get_argument('address', None),
                    zip=self.get_argument('zip', None),
                    city=self.get_argument('city', None),
                    country=self.get_argument('country', None))
                saver['invoice_ref'] = self.get_argument('invoice_ref', None)
                saver['invoice_address'] = dict(
                    address=self.get_argument('invoice_address', None),
                    zip=self.get_argument('invoice_zip', None),
                    city=self.get_argument('invoice_city', None),
                    country=self.get_argument('invoice_country', None))
                saver['phone'] = self.get_argument('phone', None)
                if not email:
                    raise ValueError('Email is required.')
                saver.set_email(email)
                saver['owner'] = saver['email']
                saver['role'] = constants.USER
                saver['status'] = constants.PENDING
                saver.check_required()
                saver.erase_password()
        except ValueError, msg:
            kwargs = OD()
            for key in self.KEYS:
                kwargs[key] = saver.get(key) or ''
            for key in self.ADDRESS_KEYS:
                kwargs[key] = saver.get('address', {}).get(key) or ''
            for key in self.ADDRESS_KEYS:
                kwargs['invoice_' + key] = saver.get('invoice_address', {}).\
                    get(key) or ''
            self.see_other('register', error=str(msg), **kwargs)
            return
        # Prepare message sent by cron job script 'script/messenger.py'
        try:
            template = settings['ACCOUNT_MESSAGES']['pending']
        except KeyError:
            pass
        else:
            account = saver.doc
            with MessageSaver(rqh=self) as saver:
                saver.set_params(
                    account=account['email'],
                    url=self.absolute_reverse_url('account', account['email']))
                saver.set_template(template)
                saver['recipients'] = [a['email'] for a in self.get_admins()]
        self.see_other('registered')


class Registered(RequestHandler):
    "Successful registration. Display message."

    def get(self):
        self.render('registered.html')


class AccountEnable(RequestHandler):
    "Enable the account; from status pending or disabled."

    @tornado.web.authenticated
    def post(self, email):
        try:
            account = self.get_account(email)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.ENABLED
            saver.reset_password()
        # Prepare message sent by cron job script 'script/messenger.py'
        try:
            template = settings['ACCOUNT_MESSAGES']['enabled']
        except KeyError:
            pass
        else:
            with MessageSaver(rqh=self) as saver:
                saver.set_params(
                    account=account['email'],
                    password_url=self.absolute_reverse_url('password'),
                    password_code_url=self.absolute_reverse_url(
                        'password',
                        email=account['email'],
                        code=account['code']),
                    code=account['code'])
                saver.set_template(template)
                saver['recipients'] = [account['email']]
        self.see_other('account', account['email'])


class AccountDisable(RequestHandler):
    "Disable the account; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        try:
            account = self.get_account(email)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other('account', account['email'])


class AccountUpdateInfo(RequestHandler):
    "Request an update of the account information by the user."

    @tornado.web.authenticated
    def post(self, email):
        try:
            account = self.get_account(email)
        except ValueError, msg:
            self.see_other('home', error=str(msg))
            return
        self.check_admin()
        if not account.get('update_info'):
            with AccountSaver(account, rqh=self) as saver:
                saver['update_info'] = True
        self.see_other('account', account['email'])
