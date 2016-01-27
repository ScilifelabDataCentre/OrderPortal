"OrderPortal: Account and login pages."

from __future__ import print_function, absolute_import

import csv
import logging
from cStringIO import StringIO

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.group import GroupSaver
from orderportal.requesthandler import RequestHandler


class AccountSaver(saver.Saver):
    doctype = constants.ACCOUNT

    def set_email(self, email):
        assert self.get('email') is None # Email must not have been set.
        if not email: raise ValueError('No email given.')
        if not constants.EMAIL_RX.match(email):
            raise ValueError('Malformed email value.')
        email = email.lower()
        if len(list(self.db.view('account/email', key=email))) > 0:
            raise ValueError('Email already in use. Do reset password if lost.')
        self['email'] = email

    def erase_password(self):
        self['password'] = None

    def set_password(self, new):
        self.check_password(new)
        self['code'] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc['password'] = utils.hashed_password(new)
        self.changed['password'] = '******'

    def check_password(self, password):
        if password is None: return
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            raise tornado.web.HTTPError(400, reason='invalid password')

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self['code'] = utils.get_iuid()


class Accounts(RequestHandler):
    "Accounts list page; just HTML, data obtained via Datatables API call."

    @tornado.web.authenticated
    def get(self):
        """HTML template output.
        Uses DataTables which calls the API to get accounts."""
        self.check_staff()
        self.render('accounts.html', params=self.get_filter_params())

    def get_filter_params(self):
        result = dict()
        for key in ['university', 'status', 'role']:
            try:
                value = self.get_argument(key)
                if not value: raise KeyError
                result[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass
        return result


class _AccountsFilter(Accounts):
    "Get accounts according to filter parameters."

    def get_accounts(self):
        params = self.get_filter_params()
        accounts = self.filter_by_university(params.get('university'))
        accounts = self.filter_by_role(params.get('role'), accounts=accounts)
        accounts = self.filter_by_status(params.get('status'),accounts=accounts)
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


class ApiV1Accounts(_AccountsFilter):
    "Accounts API; JSON"

    @tornado.web.authenticated
    def get(self):
        "JSON output."
        self.check_staff()
        accounts = self.get_accounts()
        data = []
        for account in accounts:
            name = account.get('last_name')
            first_name = account.get('first_name')
            if name:
                if first_name:
                    name += ', ' + first_name
            else:
                name = first_name
            data.append(
                dict(email=account['email'],
                     href=self.reverse_url('account', account['email']),
                     name=utils.to_utf8(name),
                     order_count=account['order_count'],
                     orders_href=
                         self.reverse_url('account_orders', account['email']),
                     university=utils.to_utf8(account['university']),
                     role=account['role'],
                     status=account['status'],
                     login=account.get('login', '-'),
                     modified=account['modified']))
        self.write(dict(data=data))


class AccountsCsv(_AccountsFilter):
    "Return a CSV file containing all data for all or filtered set of accounts."

    @tornado.web.authenticated
    def get(self):
        "CSV file output."
        self.check_staff()
        accounts = self.get_accounts()
        csvfile = StringIO()
        writer = csv.writer(csvfile)
        writer.writerow(('Email', 'Last name', 'First name', 'Role', 'Status',
                         'Order count', 'University', 'Department', 'Address',
                         'Postal code', 'City', 'Country', 'Invoice code',
                         'Invoice address', 'Invoice postal code',
                         'Invoice city', 'Invoice country', 'Phone',
                         'Other data', 'Latest login', 'Modified', 'Created'))
        for account in accounts:
            address = account.get('address') or dict()
            iaddress = account.get('invoice_address') or dict()
            writer.writerow((utils.to_utf8(account['email']),
                             utils.to_utf8(account.get('last_name') or ''),
                             utils.to_utf8(account.get('first_name') or ''),
                             account['role'],
                             account['status'],
                             account['order_count'],
                             utils.to_utf8(account.get('university') or ''),
                             utils.to_utf8(account.get('department') or ''),
                             utils.to_utf8(address.get('address') or ''),
                             utils.to_utf8(address.get('postal_code') or ''),
                             utils.to_utf8(address.get('city') or ''),
                             utils.to_utf8(address.get('country') or ''),
                             utils.to_utf8(iaddress.get('invoice_code') or ''),
                             utils.to_utf8(iaddress.get('address') or ''),
                             utils.to_utf8(iaddress.get('postal_code') or ''),
                             utils.to_utf8(iaddress.get('city') or ''),
                             utils.to_utf8(iaddress.get('country') or ''),
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
        raise tornado.web.HTTPError(403, reason='you may not read the account')

    def is_editable(self, account):
        "Is the account editable by the current user?"
        if self.is_owner(account): return True
        if self.is_staff(): return True
        return False

    def check_editable(self, account):
        "Check that the account is editable by the current user."
        if self.is_readable(account): return
        raise tornado.web.HTTPError(403, reason='you may not edit the account')


class Account(AccountMixin, RequestHandler):
    "Account page."

    @tornado.web.authenticated
    def get(self, email):
        email = email.lower()
        account = self.get_account(email)
        self.check_readable(account)
        account['order_count'] = self.get_account_order_count(email)
        view = self.db.view('log/account',
                            startkey=[email, constants.CEILING],
                            lastkey=[email],
                            descending=True,
                            limit=1)
        try:
            latest_activity = list(view)[0].key[1]
        except IndexError:
            latest_activity = None
        if self.is_staff() or self.current_user['email'] == account['email']:
            invitations = self.get_invitations(account['email'])
        else:
            invitations = []
        self.render('account.html',
                    account=account,
                    groups=self.get_account_groups(email),
                    latest_activity=latest_activity,
                    invitations=invitations,
                    is_deletable=self.is_deletable(account))

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a account that is pending; to get rid of spam application."
        email = email.lower()
        account = self.get_account(email)
        self.check_admin()
        if not self.is_deletable(account):
            raise tornado.web.HTTPError(403, reason='account cannot be deleted')
        # Delete the groups this account owns.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=email)
        for row in view:
            group = row.doc
            self.delete_logs(group['_id'])
            self.db.delete(group)
        # Remove this account from groups it is a member of.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=email)
        for row in view:
            group = row.doc
            with GroupSaver(doc=row, rqh=self) as saver:
                members = set(group['members'])
                members.discard(email)
                saver['members'] = sorted(members)
        # Delete the messages of the account.
        view = self.db.view('message/recipient',
                            reduce=False,
                            include_docs=True,
                            startkey=[email],
                            endkey=[email, constants.CEILING])
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


class AccountCurrent(RequestHandler):
    "Redirect to the account page for the current user."

    @tornado.web.authenticated
    def get(self):
        self.see_other('account', self.current_user['email'])


class AccountOrders(RequestHandler):
    "Page for a list of all orders for an account."

    def is_readable(self, account):
        "Is the account readable by the current user?"
        if account['email'] == self.current_user['email']: return True
        if self.is_staff(): return True
        if self.is_colleague(account['email']): return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.is_readable(account): return
        raise tornado.web.HTTPError(403, reason='you may not view these orders')

    @tornado.web.authenticated
    def get(self, email):
        email = email.lower()
        account = self.get_account(email)
        self.check_readable(account)
        params = dict()
        status = self.get_argument('status', None)
        # Filter by status 
        if status:
            params['status'] = status
            view = self.db.view('order/owner_status',
                                startkey=[email, status],
                                endkey=[email, status, constants.CEILING])
            page = self.get_page(view=view)
            view = self.db.view('order/owner_status',
                                reduce=False,
                                include_docs=True,
                                descending=True,
                                startkey=[email, status, constants.CEILING],
                                endkey=[email, status],
                                skip=page['start'],
                                limit=page['size'])
        else:
            view = self.db.view('order/owner',
                                startkey=[email],
                                endkey=[email, constants.CEILING])
            page = self.get_page(view=view)
            view = self.db.view('order/owner',
                                reduce=False,
                                include_docs=True,
                                descending=True,
                                startkey=[email, constants.CEILING],
                                endkey=[email],
                                skip=page['start'],
                                limit=page['size'])
        orders = [r.doc for r in view]
        self.render('account_orders.html',
                    account=account,
                    orders=orders,
                    params=params,
                    page=page)


class AccountGroupsOrders(RequestHandler):
    "Page for a list of all orders for the groups of an account."

    @tornado.web.authenticated
    def get(self, email):
        email = email.lower()
        account = self.get_account(email)
        if not (self.is_staff() or email == self.current_user['email']):
            raise tornado.web.HTTPError(403,
                                        reason='you may not view these orders')
        orders = []
        # XXX This does not scale!
        for colleague in self.get_account_colleagues(email):
            view = self.db.view('order/owner',
                                reduce=False,
                                include_docs=True,
                                startkey=[colleague],
                                endkey=[colleague, constants.CEILING])
            orders.extend([r.doc for r in view])
        params = dict()
        # Filter list
        status = self.get_argument('status', '')
        if status:
            params['status'] = status
            orders = [o for o in orders if o.get('status') == status]
        orders.sort(lambda i, j: cmp(i['modified'], j['modified']),
                    reverse=True)
        page = self.get_page(count=len(orders))
        orders = orders[page['start'] : page['end']]
        account_names = self.get_account_names([o['owner'] for o in orders])
        self.render('account_groups_orders.html',
                    account=account,
                    orders=orders,
                    account_names=account_names,
                    params=params,
                    page=page)


class AccountLogs(AccountMixin, RequestHandler):
    "Account log entries page."

    @tornado.web.authenticated
    def get(self, email):
        email = email.lower()
        account = self.get_account(email)
        self.check_readable(account)
        self.render('logs.html',
                    entity=account,
                    logs=self.get_logs(account['_id']))


class AccountMessages(AccountMixin, RequestHandler):
    "Account messages list page."

    @tornado.web.authenticated
    def get(self, email):
        "Show list of messages sent to the account given by email address."
        email = email.lower()
        account = self.get_account(email)
        self.check_readable(account)
        view = self.db.view('message/recipient',
                            startkey=[account['email']],
                            endkey=[account['email'], constants.CEILING])
        page = self.get_page(view=view)
        view = self.db.view('message/recipient',
                            descending=True,
                            startkey=[account['email'], constants.CEILING],
                            endkey=[account['email']],
                            skip=page['start'],
                            limit=page['size'],
                            reduce=False,
                            include_docs=True)
        messages = [r.doc for r in view]
        self.render('account_messages.html',
                    account=account,
                    messages=messages,
                    page=page)


class AccountEdit(AccountMixin, RequestHandler):
    "Page for editing account information."

    @tornado.web.authenticated
    def get(self, email):
        email = email.lower()
        account = self.get_account(email)
        self.check_editable(account)
        self.render('account_edit.html', account=account)

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        email = email.lower()
        account = self.get_account(email)
        self.check_editable(account)
        with AccountSaver(doc=account, rqh=self) as saver:
            # Only admin may change role of an account.
            if self.is_admin():
                role = self.get_argument('role')
                if role not in constants.ACCOUNT_ROLES:
                    raise tornado.web.HTTPError(404, reason='invalid role')
                saver['role'] = role
            saver['first_name'] = self.get_argument('first_name')
            saver['last_name'] = self.get_argument('last_name')
            university = self.get_argument('university_other', default=None)
            if not university or 'unknown' in university:
                university = self.get_argument('university', default=None)
            saver['university'] = university or None
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = dict(
                address=self.get_argument('address', default=None),
                postal_code=self.get_argument('postal_code', default=None),
                city=self.get_argument('city', default=None),
                country=self.get_argument('country', default=None))
            saver['invoice_address'] = dict(
                invoice_code=self.get_argument('invoice_code', default=None),
                address=self.get_argument('invoice_address', default=None),
                postal_code=self.get_argument('invoice_postal_code', default=None),
                city=self.get_argument('invoice_city', default=None),
                country=self.get_argument('invoice_country', default=None))
            saver['phone'] = self.get_argument('phone', default=None)
            try:
                value = int(self.get_argument('page_size', 0))
                if value <= 1:
                    raise ValueError
            except (ValueError, TypeError):
                saver['page_size'] = None
            else:
                saver['page_size'] = value
            saver['other_data'] = self.get_argument('other_data', default=None)
            saver['update_info'] = False
        self.see_other('account', email)


class Login(RequestHandler):
    "Login to a account account. Set a secure cookie."

    def get(self):
        self.render('login.html', next=self.get_argument('next', None))

    def post(self):
        "Login to a account account. Set a secure cookie."
        self.check_xsrf_cookie()
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
            account = self.get_account(email)
            if not utils.hashed_password(password) == account.get('password'):
                raise ValueError('invalid password')
            if not account.get('status') == constants.ENABLED:
                raise ValueError('disabled account account')
        except (tornado.web.MissingArgumentError,
                tornado.web.HTTPError,
                ValueError), msg:
            self.see_other('home',
                           error='Invalid email (=username) or password.')
        else:
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
                               message='Please update your account information.')
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
        self.check_xsrf_cookie()
        self.set_secure_cookie(constants.USER_COOKIE, '')
        self.redirect(self.reverse_url('home'))


class Reset(RequestHandler):
    "Reset the password of a account account."

    def get(self):
        self.render('reset.html', email=self.get_argument('account', ''))

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.reset_password()
        if self.current_user and self.current_user['email'] == account['email']:
            self.see_other('password')
        else:
            self.see_other('home')


class Password(RequestHandler):
    "Set the password of a account account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        if account.get('code') != self.get_argument('code'):
            raise tornado.web.HTTPError(400, reason='invalid email or code')
        password = self.get_argument('password')
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            mgs = "password shorter than {0} characters".format(
                constants.MIN_PASSWORD_LENGTH)
            raise tornado.web.HTTPError(400, reason=msg)
        if password != self.get_argument('confirm_password'):
            msg = 'password not the same! mistyped'
            raise tornado.web.HTTPError(400, reason=msg)
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, account['email'],
                               expires_days=settings['LOGIN_MAX_AGE_DAYS'])
        if account.get('update_info'):
            self.see_other('account_edit', account['email'],
                           message='Please update your account information.')
        else:
            self.redirect(self.reverse_url('home'))


class Register(RequestHandler):
    "Register a new account account."

    def get(self):
        if not self.global_modes['allow_registration']:
            self.see_other('home', error='Registration is currently disabled.')
            return
        self.render('register.html')

    def post(self):
        if not self.global_modes['allow_registration']:
            self.see_other('home', error='Registration is currently disabled.')
            return
        self.check_xsrf_cookie()
        with AccountSaver(rqh=self) as saver:
            try:
                email = self.get_argument('email', '')
                saver.set_email(email)
            except ValueError, msg:
                self.see_other('register', error=str(msg))
                # raise tornado.web.HTTPError(400, reason=str(msg))
            try:
                saver['first_name'] = self.get_argument('first_name')
                saver['last_name'] = self.get_argument('last_name')
                university = self.get_argument('university_other', default=None)
                if not university:
                    university = self.get_argument('university', default=None)
                saver['university'] = university or None
            except (tornado.web.MissingArgumentError, ValueError):
                reason = u"invalid '{0}' value provided".format(key)
                raise tornado.web.HTTPError(400, reason=reason)
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = dict(
                address=self.get_argument('address', default=None),
                postal_code=self.get_argument('postal_code', default=None),
                city=self.get_argument('city', default=None),
                country=self.get_argument('country', default=None))
            saver['invoice_address'] = dict(
                invoice_code=self.get_argument('invoice_code', default=None),
                address=self.get_argument('invoice_address', default=None),
                postal_code=self.get_argument('invoice_postal_code', default=None),
                city=self.get_argument('invoice_city', default=None),
                country=self.get_argument('invoice_country', default=None))
            if not saver['invoice_address'].get('address'):
                try:
                    saver['invoice_address'] = \
                        settings['UNIVERSITIES'][saver['university']]['invoice_address']
                except KeyError:
                    pass
            saver['phone'] = self.get_argument('phone', default=None)
            saver['owner'] = email
            saver['role'] = constants.USER
            saver['status'] = constants.PENDING
            saver.erase_password()
        self.see_other('registered')


class Registered(RequestHandler):
    "Successful registration. Display message."

    def get(self):
        self.render('registered.html')


class AccountEnable(RequestHandler):
    "Enable the account; from status pending or disabled."


    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.ENABLED
            saver.reset_password()
        self.see_other('account', email)


class AccountDisable(RequestHandler):
    "Disable the account; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other('account', email)
