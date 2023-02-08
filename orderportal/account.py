"Account and login pages."

import csv
import logging

import tornado.web

import orderportal
from orderportal import constants, settings, parameters
from orderportal import saver
from orderportal import utils
from orderportal.order import OrderApiV1Mixin
from orderportal.group import GroupSaver
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler


DESIGN_DOC = {
    "views": {
        "all": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.modified, null);
}"""},
        "api_key": {
            "map": """function(doc) { 
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}"""},
        "email": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}"""},
        "role": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}"""},
        "status": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}"""},
        "university": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}"""}
    }
}


class AccountSaver(saver.Saver):
    doctype = constants.ACCOUNT

    def set_email(self, email):
        assert self.get("email") is None  # Email must not have been set.
        email = email.strip().lower()
        if not email:
            raise ValueError("No email given.")
        if not constants.EMAIL_RX.match(email):
            raise ValueError("Malformed email value.")
        if len(list(self.db.view("account", "email", key=email))) > 0:
            raise ValueError(
                "Email is already in use." " Use 'Reset password' if you have lost it."
            )
        self["email"] = email

    def erase_password(self):
        self["password"] = None

    def set_password(self, new):
        utils.check_password(new)
        self["code"] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc["password"] = utils.hashed_password(new)
        self.changed["password"] = "******"

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self["code"] = utils.get_iuid()

    def check_required(self):
        "Check that required data is present. Raise ValueError otherwise."
        if not self["first_name"]:
            raise ValueError("First name is required.")
        if not self["last_name"]:
            raise ValueError("Last name is required.")
        if not self["university"]:
            raise ValueError("University is required.")
        if settings["ACCOUNT_INVOICE_REF_REQUIRED"]:
            if not self["invoice_ref"]:
                raise ValueError("Invoice reference is required.")


class Accounts(RequestHandler):
    "Accounts list page."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        self.set_filter()
        self.render("account/list.html", accounts=self.get_accounts(), filter=self.filter)

    def set_filter(self):
        "Set the filter parameters dictionary."
        self.filter = dict()
        for key in ["university", "status", "role"]:
            try:
                value = self.get_argument(key)
                if not value:
                    raise KeyError
                self.filter[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass

    def get_accounts(self):
        "Get the accounts."
        accounts = self.filter_by_university(self.filter.get("university"))
        accounts = self.filter_by_role(self.filter.get("role"), accounts=accounts)
        accounts = self.filter_by_status(self.filter.get("status"), accounts=accounts)
        # No filter; all accounts
        if accounts is None:
            view = self.db.view("account", "email", include_docs=True)
            accounts = [r.doc for r in view]
        # This is optimized for retrieval speed. The single-valued
        # function 'get_account_order_count' is not good enough here.
        view = self.db.view(
            "order", "owner", group_level=1, startkey=[""], endkey=[constants.CEILING]
        )
        counts = dict([(r.key[0], r.value) for r in view])
        for account in accounts:
            account["order_count"] = counts.get(account["email"], 0)
            account["name"] = ", ".join([n for n in [account.get("last_name"),
                                                     account.get("first_name")]
                                         if n])
        return accounts

    def filter_by_university(self, university, accounts=None):
        "Return accounts list if any university filter, or None if none."
        if university == "[other]":
            if accounts is None:
                view = self.db.view("account", "email", include_docs=True)
                accounts = [r.doc for r in view]
            accounts = [
                a for a in accounts if a["university"] not in settings["UNIVERSITIES"]
            ]
        elif university:
            if accounts is None:
                view = self.db.view(
                    "account", "university", key=university, include_docs=True
                )
                accounts = [r.doc for r in view]
            else:
                account = [a for a in accounts if a["university"] == university]
        return accounts

    def filter_by_role(self, role, accounts=None):
        "Return accounts list if any role filter, or None if none."
        if role:
            if accounts is None:
                view = self.db.view("account", "role", key=role, include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [a for a in accounts if a["role"] == role]
        return accounts

    def filter_by_status(self, status, accounts=None):
        "Return accounts list if any status filter, or None if none."
        if status:
            if accounts is None:
                view = self.db.view("account", "status", key=status, include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [a for a in accounts if a["status"] == status]
        return accounts


class AccountsApiV1(Accounts):
    "Accounts API; JSON output."

    def get(self):
        "JSON output."
        URL = self.absolute_reverse_url
        self.check_staff()
        self.set_filter()
        accounts = self.get_accounts()
        data = utils.get_json(URL("accounts_api", **self.filter), "accounts")
        data["filter"] = self.filter
        data["links"] = dict(
            api=dict(href=URL("accounts_api")), display=dict(href=URL("accounts"))
        )
        data["items"] = []
        for account in accounts:
            item = dict()
            item["email"] = account["email"]
            item["links"] = dict(
                api=dict(href=URL("account_api", account["email"])),
                display=dict(href=URL("account", account["email"])),
            )
            name = last_name = account.get("last_name")
            first_name = account.get("first_name")
            if name:
                if first_name:
                    name += ", " + first_name
            else:
                name = first_name
            item["name"] = name
            item["first_name"] = first_name
            item["last_name"] = last_name
            item["pi"] = bool(account.get("pi"))
            item["orcid"] = bool(account.get("orcid"))
            item["gender"] = account.get("gender")
            item["university"] = account.get("university")
            item["role"] = account["role"]
            item["status"] = account["status"]
            item["address"] = account.get("address") or {}
            item["invoice_ref"] = account.get("invoice_ref")
            item["invoice_address"] = account.get("invoice_address") or {}
            item["login"] = account.get("login", "-")
            item["modified"] = account["modified"]
            item["orders"] = dict(
                count=account["order_count"],
                links=dict(
                    display=dict(href=URL("account_orders", account["email"])),
                    api=dict(href=URL("account_orders_api", account["email"])),
                ),
            )
            data["items"].append(item)
        self.write(data)


class AccountsCsv(Accounts):
    "Return a CSV file containing all data for a set of accounts."

    @tornado.web.authenticated
    def get(self):
        "CSV file output."
        self.check_staff()
        self.set_filter()
        accounts = self.get_accounts()
        writer = self.get_writer()
        writer.writerow((settings["SITE_NAME"], utils.today()))
        writer.writerow(
            (
                "Email",
                "Last name",
                "First name",
                "Role",
                "Status",
                "Order count",
                "University",
                "Department",
                "PI",
                "ORCID",
                "Gender",
                "Group size",
                "Subject",
                "Address",
                "Zip",
                "City",
                "Country",
                "Invoice ref",
                "Invoice address",
                "Invoice zip",
                "Invoice city",
                "Invoice country",
                "Phone",
                "Other data",
                "Latest login",
                "Modified",
                "Created",
            )
        )
        for account in accounts:
            addr = account.get("address") or dict()
            iaddr = account.get("invoice_address") or dict()
            try:
                subject = "{0}: {1}".format(
                    account.get("subject"),
                    settings["SUBJECT_TERMS_LOOKUP"][account.get("subject")],
                )
            except KeyError:
                subject = ""
            row = [
                account["email"],
                account.get("last_name") or "",
                account.get("first_name") or "",
                account["role"],
                account["status"],
                account["order_count"],
                account.get("university") or "",
                account.get("department") or "",
                account.get("pi") and "yes" or "no",
                account.get("orcid") or "",
                account.get("gender") or "",
                account.get("group_size") or "",
                subject,
                addr.get("address") or "",
                addr.get("zip") or "",
                addr.get("city") or "",
                addr.get("country") or "",
                account.get("invoice_ref") or "",
                iaddr.get("address") or "",
                iaddr.get("zip") or "",
                iaddr.get("city") or "",
                iaddr.get("country") or "",
                account.get("phone") or "",
                account.get("other_data") or "",
                account.get("login") or "",
                account.get("modified") or "",
                account.get("created") or "",
            ]
            writer.writerow(row)
        self.write(writer.getvalue())
        self.write_finish()

    def get_writer(self):
        return utils.CsvWriter()

    def write_finish(self):
        self.set_header("Content-Type", constants.CSV_MIMETYPE)
        self.set_header("Content-Disposition", 'attachment; filename="accounts.csv"')


class AccountsXlsx(AccountsCsv):
    "Return an XLSX file containing all data for a set of accounts."

    def get_writer(self):
        return utils.XlsxWriter()

    def write_finish(self):
        self.set_header("Content-Type", constants.XLSX_MIMETYPE)
        self.set_header("Content-Disposition", 'attachment; filename="accounts.xlsx"')


class AccountMixin(object):
    "Mixin for various useful methods."

    def allow_read(self, account):
        "Is the account readable by the current user?"
        if self.is_owner(account):
            return True
        if self.is_staff():
            return True
        if self.is_colleague(account["email"]):
            return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.allow_read(account):
            return
        raise ValueError("You may not read the account.")

    def allow_edit(self, account):
        "Is the account editable by the current user?"
        if self.is_owner(account):
            return True
        if self.is_staff():
            return True
        return False

    def check_editable(self, account):
        "Check that the account is editable by the current user."
        if self.allow_read(account):
            return
        raise ValueError("You may not edit the account.")


class Account(AccountMixin, RequestHandler):
    "Account page."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        account["order_count"] = self.get_account_order_count(account["email"])
        view = self.db.view(
            "log",
            "account",
            startkey=[account["email"], constants.CEILING],
            endkey=[account["email"]],
            descending=True,
            limit=1,
        )
        try:
            key = list(view)[0].key
            if key[0] != account["email"]:
                raise IndexError
            latest_activity = key[1]
        except IndexError:
            latest_activity = None
        if self.is_staff() or self.current_user["email"] == account["email"]:
            invitations = self.get_invitations(account["email"])
        else:
            invitations = []
        self.render(
            "account/display.html",
            account=account,
            groups=self.get_account_groups(account["email"]),
            latest_activity=latest_activity,
            invitations=invitations,
            allow_delete=self.allow_delete(account),
        )

    @tornado.web.authenticated
    def post(self, email):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(email)
            return
        raise tornado.web.HTTPError(
            405, reason="Internal problem; POST only allowed for DELETE."
        )

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a account that is pending; to get rid of spam application."
        account = self.get_account(email)
        self.check_staff()
        if not self.allow_delete(account):
            self.see_other(
                "account", account["email"], error="Account cannot be deleted."
            )
            return
        # Delete the groups this account owns.
        view = self.db.view("group", "owner", include_docs=True, key=account["email"])
        for row in view:
            group = row.doc
            self.delete_logs(group["_id"])
            self.db.delete(group)
        # Remove this account from groups it is a member of.
        view = self.db.view("group", "owner", include_docs=True, key=account["email"])
        for row in view:
            group = row.doc
            with GroupSaver(doc=row, rqh=self) as saver:
                members = set(group["members"])
                members.discard(account["email"])
                saver["members"] = sorted(members)
        # Delete the messages of the account.
        view = self.db.view(
            "message",
            "recipient",
            reduce=False,
            include_docs=True,
            startkey=[account["email"]],
            endkey=[account["email"], constants.CEILING],
        )
        for row in view:
            message = row.doc
            self.delete_logs(message["_id"])
            self.db.delete(message)
        # Delete the logs of the account.
        self.delete_logs(account["_id"])
        # Delete the account itself.
        self.db.delete(account)
        self.see_other("accounts")

    def allow_delete(self, account):
        "Can the account be deleted? Pending, or disabled and no orders."
        if account["status"] == constants.PENDING:
            return True
        if account["status"] == constants.ENABLED:
            return False
        if self.get_account_order_count(account["email"]) == 0:
            return True
        return False


class AccountApiV1(AccountMixin, RequestHandler):
    "Account API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(account)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        data = utils.get_json(URL("account", email), "account")
        data["email"] = account["email"]
        name = last_name = account.get("last_name")
        first_name = account.get("first_name")
        if name:
            if first_name:
                name += ", " + first_name
        else:
            name = first_name
        data["links"] = dict(
            api=dict(href=URL("account_api", account["email"])),
            display=dict(href=URL("account", account["email"])),
        )
        data["name"] = name
        data["first_name"] = first_name
        data["last_name"] = last_name
        data["pi"] = bool(account.get("pi"))
        data["university"] = account["university"]
        data["role"] = account["role"]
        data["orcid"] = account.get("orcid")
        data["gender"] = account.get("gender")
        data["group_size"] = account.get("group_size")
        data["status"] = account["status"]
        data["address"] = account.get("address") or {}
        data["invoice_ref"] = account.get("invoice_ref")
        data["invoice_address"] = account.get("invoice_address") or {}
        data["login"] = account.get("login", "-")
        data["modified"] = account["modified"]
        view = self.db.view(
            "log",
            "account",
            startkey=[account["email"], constants.CEILING],
            endkey=[account["email"]],
            descending=True,
            limit=1,
        )
        try:
            data["latest_activity"] = list(view)[0].key[1]
        except IndexError:
            data["latest_activity"] = None
        data["orders"] = dict(
            count=self.get_account_order_count(account["email"]),
            display=dict(href=URL("account_orders", account["email"])),
            api=dict(href=URL("account_orders_api", account["email"])),
        )
        self.write(data)


class AccountOrdersMixin(object):
    "Mixin containing access tests."

    def allow_read(self, account):
        "Is the account readable by the current user?"
        if account["email"] == self.current_user["email"]:
            return True
        if self.is_staff():
            return True
        if self.is_colleague(account["email"]):
            return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.allow_read(account):
            return
        raise ValueError("You may not view these orders.")

    def get_group_orders(self, account):
        "Return all orders for the accounts in the account's group."
        orders = []
        for colleague in self.get_account_colleagues(account["email"]):
            view = self.db.view(
                "order",
                "owner",
                reduce=False,
                include_docs=True,
                startkey=[colleague],
                endkey=[colleague, constants.CEILING],
            )
            orders.extend([r.doc for r in view])
        return orders


class AccountOrders(AccountOrdersMixin, RequestHandler):
    "Page for a list of all orders for an account."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        # Default ordering by the 'modified' column.
        if parameters["DEFAULT_ORDER_COLUMN"] == "modified":
            order_column = (
                int(parameters["ORDERS_LIST_TAGS"]) # boolean
                + len(parameters["ORDERS_LIST_FIELDS"]) # list
                + len(parameters["ORDERS_LIST_STATUSES"]) # list
            )
            if self.is_staff():
                order_column += 1
        # Otherwise default ordering by the identifier column.
        else:
            order_column = 0
        view = self.db.view(
            "order",
            "owner",
            reduce=False,
            include_docs=True,
            startkey=[account["email"]],
            endkey=[account["email"], constants.CEILING],
        )
        orders = [r.doc for r in view]
        self.render(
            "account/orders.html",
            forms_lookup=self.get_forms_lookup(),
            orders=orders,
            account=account,
            order_column=order_column,
            account_names=self.get_accounts_name(),
            any_groups=bool(self.get_account_groups(account["email"])),
        )


class AccountOrdersApiV1(AccountOrdersMixin, OrderApiV1Mixin, RequestHandler):
    "Account orders API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        "JSON output."
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(account)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        account_names = self.get_accounts_name()
        forms_lookup = self.get_forms_lookup()
        data = utils.get_json(URL("account_orders", account["email"]), "account orders")
        data["links"] = dict(
            api=dict(href=URL("account_orders_api", account["email"])),
            display=dict(href=URL("account_orders", account["email"])),
        )
        view = self.db.view(
            "order",
            "owner",
            reduce=False,
            include_docs=True,
            startkey=[account["email"]],
            endkey=[account["email"], constants.CEILING],
        )
        data["orders"] = [
            self.get_order_json(
                r.doc, account_names=account_names, forms_lookup=forms_lookup
            )
            for r in view
        ]
        self.write(data)


class AccountGroupsOrders(AccountOrdersMixin, RequestHandler):
    "Page for a list of all orders for the groups of an account."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        # Default ordering by the 'modified' column.
        if parameters["DEFAULT_ORDER_COLUMN"] == "modified":
            order_column = (
                int(parameters["ORDERS_LIST_TAGS"]) # boolean
                + len(parameters["ORDERS_LIST_FIELDS"]) # list
                + len(parameters["ORDERS_LIST_STATUSES"]) # list
            )
            if self.is_staff():
                order_column += 1
        # Otherwise default ordering by the identifier column.
        else:
            order_column = 0
        self.render(
            "account/groups_orders.html",
            account=account,
            forms_lookup=self.get_forms_lookup(),
            orders=self.get_group_orders(account),
            order_column=order_column,
        )


class AccountGroupsOrdersApiV1(AccountOrdersMixin, OrderApiV1Mixin, RequestHandler):
    "Account group orders API; JSON output."

    @tornado.web.authenticated
    def get(self, email):
        "JSON output."
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(email)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(account)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        account_names = self.get_accounts_name()
        forms_lookup = self.get_forms_lookup()
        data = utils.get_json(
            URL("account_groups_orders_api", account["email"]), "account groups orders"
        )
        data["links"] = dict(
            api=dict(href=URL("account_groups_orders_api", account["email"])),
            display=dict(href=URL("account_groups_orders", account["email"])),
        )
        data["orders"] = [
            self.get_order_json(
                o, account_names=account_names, forms_lookup=forms_lookup
            )
            for o in self.get_group_orders(account)
        ]
        self.write(data)


class AccountLogs(AccountMixin, RequestHandler):
    "Account log entries page."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        self.render("logs.html", entity=account, logs=self.get_logs(account["_id"]))


class AccountMessages(AccountMixin, RequestHandler):
    "Account messages list page."

    @tornado.web.authenticated
    def get(self, email):
        "Show list of messages sent to the account given by email address."
        try:
            account = self.get_account(email)
            self.check_readable(account)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        view = self.db.view(
            "message",
            "recipient",
            startkey=[account["email"]],
            endkey=[account["email"], constants.CEILING],
        )
        view = self.db.view(
            "message",
            "recipient",
            descending=True,
            startkey=[account["email"], constants.CEILING],
            endkey=[account["email"]],
            reduce=False,
            include_docs=True,
        )
        messages = [r.doc for r in view]
        self.render("account/messages.html", account=account, messages=messages)


class AccountEdit(AccountMixin, RequestHandler):
    "Page for editing account information."

    @tornado.web.authenticated
    def get(self, email):
        try:
            account = self.get_account(email)
            self.check_editable(account)
        except ValueError as msg:
            self.see_other("account", account["email"], error=str(msg))
            return
        self.render("account/edit.html", account=account)

    @tornado.web.authenticated
    def post(self, email):
        try:
            account = self.get_account(email)
            self.check_editable(account)
        except ValueError as msg:
            self.see_other("account_edit", account["email"], error=str(msg))
            return
        try:
            with AccountSaver(doc=account, rqh=self) as saver:
                # Only admin (not staff!) may change role of an account.
                if self.is_admin():
                    role = self.get_argument("role")
                    if role not in constants.ACCOUNT_ROLES:
                        raise ValueError("Invalid role.")
                    saver["role"] = role
                saver["first_name"] = self.get_argument("first_name")
                saver["last_name"] = self.get_argument("last_name")
                university = self.get_argument("university", None)
                if not university:
                    university = self.get_argument("university_other", None)
                saver["university"] = university
                saver["department"] = self.get_argument("department", None)
                saver["pi"] = utils.to_bool(self.get_argument("pi", False))
                saver["orcid"] = self.get_argument("orcid", None)
                try:
                    saver["gender"] = self.get_argument("gender").lower()
                except tornado.web.MissingArgumentError:
                    saver.doc.pop("gender", None)
                try:
                    saver["group_size"] = self.get_argument("group_size")
                except tornado.web.MissingArgumentError:
                    saver.doc.pop("group_size", None)
                try:
                    saver["subject"] = int(self.get_argument("subject"))
                except (tornado.web.MissingArgumentError, ValueError, TypeError):
                    saver["subject"] = None
                saver["address"] = dict(
                    address=self.get_argument("address", None),
                    zip=self.get_argument("zip", None),
                    city=self.get_argument("city", None),
                    country=self.get_argument("country", None),
                )
                saver["invoice_ref"] = self.get_argument("invoice_ref", None)
                saver["invoice_address"] = dict(
                    address=self.get_argument("invoice_address", None),
                    zip=self.get_argument("invoice_zip", None),
                    city=self.get_argument("invoice_city", None),
                    country=self.get_argument("invoice_country", None),
                )
                saver["phone"] = self.get_argument("phone", None)
                saver["other_data"] = self.get_argument("other_data", None)
                if utils.to_bool(self.get_argument("api_key", False)):
                    saver["api_key"] = utils.get_iuid()
                saver["update_info"] = False
                saver.check_required()
        except ValueError as msg:
            self.see_other("account_edit", account["email"], error=str(msg))
        else:
            self.see_other("account", account["email"])


class LoginMixin:

    def do_login(self, account):
        self.set_secure_cookie(
            constants.USER_COOKIE,
            account["email"],
            expires_days=settings["LOGIN_MAX_AGE_DAYS"],
        )
        with AccountSaver(doc=account, rqh=self) as saver:
            saver["login"] = utils.timestamp()  # Set login timestamp.

    def do_logout(self):
        self.set_secure_cookie(constants.USER_COOKIE, "")


class Login(LoginMixin, RequestHandler):
    "Login to a account account. Set a secure cookie."

    def get(self):
        self.render("account/login.html")

    def post(self):
        """Login to a account account. Set a secure cookie.
        Forward to account edit page if first login.
        Log failed login attempt. Disable account if too many recent.
        """
        try:
            email = self.get_argument("email")
            password = self.get_argument("password")
        except tornado.web.MissingArgumentError:
            self.see_other("home", error="Missing email or password argument.")
            return
        msg = "Sorry, no such account or invalid password."
        try:
            account = self.get_account(email)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        if utils.hashed_password(password) != account.get("password"):
            utils.log(
                self.db, self, account, changed=dict(login_failure=account["email"])
            )
            view = self.db.view(
                "log",
                "login_failure",
                startkey=[account["_id"], utils.timestamp(-1)],
                endkey=[account["_id"], utils.timestamp()],
            )
            # Disable account if too many recent login failures.
            if len(list(view)) > settings["LOGIN_MAX_FAILURES"]:
                logging.warning(
                    f"account {account['email']} has been disabled due to too many login failures"
                )
                with AccountSaver(doc=account, rqh=self) as saver:
                    saver["status"] = constants.DISABLED
                    saver.erase_password()
                msg = "Too many failed login attempts: Your account has been disabled. Contact the admin"
                # Prepare email message about being disabled.
                text = parameters[constants.ACCOUNT][constants.DISABLED]
                with MessageSaver(rqh=self) as saver:
                    saver.create(text)
                    saver.send(self.get_recipients(text, account))
            self.see_other("home", error=msg)
            return
        try:
            if not account.get("status") == constants.ENABLED:
                raise ValueError
        except ValueError:
            msg = "Account is disabled. Contact the admin."
            self.see_other("home", error=msg)
            return
        logging.debug(f"Basic auth login: account {account['email']}")
        self.do_login(account)
        if account.get("update_info"):
            self.see_other(
                "account_edit",
                account["email"],
                message="Please review and update your account information.",
            )
            return
        # Not quite right: should be an absolute URL to redirect.
        # But seems to work anyway.
        self.see_other("home")

class Logout(LoginMixin, RequestHandler):
    "Logout; unset the secure cookie, and invalidate login session."

    @tornado.web.authenticated
    def post(self):
        self.do_logout()
        self.see_other("home")


class Reset(LoginMixin, RequestHandler):
    "Reset the password of an account."

    def get(self):
        self.render("account/reset.html", email=self.get_argument("email", ""))

    def post(self):
        URL = self.absolute_reverse_url
        try:
            account = self.get_account(self.get_argument("email"))
        except (tornado.web.MissingArgumentError, ValueError):
            self.see_other("home")  # Silent error! Should not show existence.
        else:
            if account.get("status") == constants.PENDING:
                self.see_other(
                    "home", error="Cannot reset password. Account has not been enabled."
                )
                return
            elif account.get("status") == constants.DISABLED:
                self.see_other(
                    "home",
                    error="Cannot reset password. Account is disabled; contact the admin.",
                )
                return
            with AccountSaver(doc=account, rqh=self) as saver:
                saver.reset_password()
            text = parameters[constants.ACCOUNT][constants.RESET]
            try:
                with MessageSaver(rqh=self) as saver:
                    saver.create(
                        text,
                        account=account["email"],
                        url=URL("password"),
                        password_url=URL("password"),
                        password_code_url=URL(
                            "password", email=account["email"], code=account["code"]
                        ),
                        code=account["code"],
                    )
                    saver.send(self.get_recipients(text, account))
                    # Log out the user if same as the account that was reset.
                    if self.current_user == account:
                        self.do_logout()
            except KeyError as error:
                self.see_other("home", message=str(error))
            except ValueError as error:
                self.see_other("home", error=str(error))
            else:
                self.see_other(
                    "home",
                    message="An email has been sent containing a reset code. Use the link in the email.",
                )


class Password(LoginMixin, RequestHandler):
    "Set the password of a account account; requires a code."

    def get(self):
        self.render(
            "account/password.html",
            title="Set your password",
            email=self.get_argument("email", default=""),
            code=self.get_argument("code", default=""),
        )

    def post(self):
        try:
            account = self.get_account(self.get_argument("email", ""))
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        if not self.is_staff() and (account.get("code") != self.get_argument("code")):
            self.see_other(
                "home",
                error="Either the email address or the code for setting password was"
                " wrong.Try to request a new code using the 'Reset password' button."
            )
            return
        password = self.get_argument("password", "")
        try:
            utils.check_password(password)
        except ValueError as msg:
            self.see_other(
                "password",
                email=self.get_argument("email") or "",
                code=self.get_argument("code") or "",
                error=str(msg),
            )
            return
        if password != self.get_argument("confirm_password"):
            self.see_other(
                "password",
                email=self.get_argument("email") or "",
                code=self.get_argument("code") or "",
                error="Password confirmation failed. Not the same!",
            )

        with AccountSaver(doc=account, rqh=self) as saver:
            saver.set_password(password)
        if not self.current_user:
            self.do_login(account)
        self.see_other("home", message="Password set.")


class Register(RequestHandler):
    "Register a new account account."

    KEYS = [
        "email",
        "first_name",
        "last_name",
        "university",
        "department",
        "pi",
        "orcid",
        "gender",
        "group_size",
        "subject",
        "invoice_ref",
        "phone",
    ]
    ADDRESS_KEYS = ["address", "zip", "city", "country"]

    def get(self):
        values = dict()
        for key in self.KEYS:
            values[key] = self.get_argument(key, None)
        for key in self.ADDRESS_KEYS:
            values[key] = self.get_argument(key, None)
        for key in self.ADDRESS_KEYS:
            values["invoice_" + key] = self.get_argument("invoice_" + key, None)
        self.render("account/register.html", values=values)

    def post(self):
        try:
            with AccountSaver(rqh=self) as saver:
                email = self.get_argument("email", None)
                saver["first_name"] = self.get_argument("first_name", None)
                saver["last_name"] = self.get_argument("last_name", None)
                university = self.get_argument("university", None)
                if not university:
                    university = self.get_argument("university_other", None)
                saver["university"] = university
                saver["department"] = self.get_argument("department", None)
                saver["pi"] = utils.to_bool(self.get_argument("pi", False))
                saver["orcid"] = self.get_argument("orcid", None)
                gender = self.get_argument("gender", None)
                if gender:
                    saver["gender"] = gender.lower()
                group_size = self.get_argument("group_size", None)
                if group_size:
                    saver["group_size"] = group_size
                try:
                    saver["subject"] = int(self.get_argument("subject"))
                except (tornado.web.MissingArgumentError, ValueError, TypeError):
                    saver["subject"] = None
                saver["address"] = dict(
                    address=self.get_argument("address", None),
                    zip=self.get_argument("zip", None),
                    city=self.get_argument("city", None),
                    country=self.get_argument("country", None),
                )
                saver["invoice_ref"] = self.get_argument("invoice_ref", None)
                saver["invoice_address"] = dict(
                    address=self.get_argument("invoice_address", None),
                    zip=self.get_argument("invoice_zip", None),
                    city=self.get_argument("invoice_city", None),
                    country=self.get_argument("invoice_country", None),
                )
                saver["phone"] = self.get_argument("phone", None)
                if not email:
                    raise ValueError("Email is required.")
                saver.set_email(email)
                saver.check_required()
                saver["owner"] = saver["email"]
                saver["role"] = constants.USER
                saver["api_key"] = utils.get_iuid()
                if self.is_staff():
                    saver["status"] = constants.ENABLED
                    saver.reset_password()
                else:
                    saver["status"] = constants.PENDING
                    saver.erase_password()
        except ValueError as msg:
            kwargs = dict()
            for key in self.KEYS:
                kwargs[key] = saver.get(key) or ""
            for key in self.ADDRESS_KEYS:
                kwargs[key] = saver.get("address", {}).get(key) or ""
            for key in self.ADDRESS_KEYS:
                kwargs["invoice_" + key] = (
                    saver.get("invoice_address", {}).get(key) or ""
                )
            self.see_other("register", error=str(msg), **kwargs)
            return
        account = saver.doc
        text = parameters[constants.ACCOUNT][account["status"]]
        # Allow staff to avoid sending email to the person when registering an account.
        if not (
            self.is_staff()
            and not utils.to_bool(self.get_argument("send_email", False))
        ):
            try:
                with MessageSaver(rqh=self) as saver:
                    saver.create(
                        text,
                        account=account["email"],
                        url=self.absolute_reverse_url("account", account["email"]),
                        password_url=self.absolute_reverse_url("password"),
                        password_code_url=self.absolute_reverse_url(
                            "password", email=account["email"], code=account["code"]
                        ),
                        code=account["code"],
                    )
                    saver.send(self.get_recipients(text, account))
            except KeyError as error:
                self.set_message_flash(str(error))
            except ValueError as error:
                self.set_error_flash(str(error))
        if self.is_staff():
            self.see_other("account", account["email"])
        else:
            self.see_other("registered")


class Registered(RequestHandler):
    "Successful registration. Display message."

    def get(self):
        self.render("account/registered.html")


class AccountEnable(RequestHandler):
    "Enable the account; from status pending or disabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_staff()
        try:
            account = self.get_account(email)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        with AccountSaver(account, rqh=self) as saver:
            saver["status"] = constants.ENABLED
            saver.reset_password()
        text = parameters[constants.ACCOUNT][constants.ENABLED]
        with MessageSaver(rqh=self) as saver:
            saver.create(
                text,
                account=account["email"],
                password_url=self.absolute_reverse_url("password"),
                password_code_url=self.absolute_reverse_url(
                    "password", email=account["email"], code=account["code"]
                ),
                code=account["code"],
            )
            saver.send(self.get_recipients(text, account))
        self.see_other("account", account["email"])


class AccountDisable(RequestHandler):
    "Disable the account; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_staff()
        try:
            account = self.get_account(email)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        with AccountSaver(account, rqh=self) as saver:
            saver["status"] = constants.DISABLED
            saver.erase_password()
        # No message sent here.Only done when user has too many login failures; above.
        self.see_other("account", account["email"])


class AccountUpdateInfo(RequestHandler):
    "Request an update of the account information by the user."

    @tornado.web.authenticated
    def post(self, email):
        self.check_staff()
        try:
            account = self.get_account(email)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        if not account.get("update_info"):
            with AccountSaver(account, rqh=self) as saver:
                saver["update_info"] = True
        self.see_other("account", account["email"])
