"Group pages; accounts which are able to see all orders of each other."

import tornado.web

import orderportal
from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class GroupSaver(saver.Saver):
    doctype = constants.GROUP


class GroupMixin:
    "Mixin for access check methods."

    def check_readable(self, group):
        "Check if current user may read the group."
        if self.am_owner(group):
            return
        if self.current_user["email"] in group["members"]:
            return
        if self.am_staff():
            return
        raise ValueError("you may not read the group")

    def allow_edit(self, group):
        "Is the group editable by the current user?"
        if self.am_admin():
            return True
        if self.am_owner(group):
            return True
        return False

    def check_editable(self, group):
        "Check if current user may edit the group."
        if not self.allow_edit(group):
            raise ValueError("you may not edit the group")


class Group(GroupMixin, RequestHandler):
    "Display group."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_group(iuid)
        try:
            self.check_readable(group)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        self.render(
            "group/display.html", group=group, allow_edit=self.allow_edit(group)
        )

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason="POST only allowed for DELETE")

    @tornado.web.authenticated
    def delete(self, iuid):
        group = self.get_group(iuid)
        self.check_editable(group)
        self.delete_logs(group["_id"])
        self.db.delete(group)
        self.see_other("account", self.current_user["email"])


class GroupCreate(RequestHandler):
    "Create group."

    @tornado.web.authenticated
    def get(self):
        self.render("group/create.html")

    @tornado.web.authenticated
    def post(self):
        with GroupSaver(rqh=self) as saver:
            saver["name"] = self.get_argument("name", "") or "[no name]"
            saver["owner"] = self.current_user["email"]
            invited = set()
            value = self.get_argument("invited", "").replace(",", " ").strip()
            for email in value.split():
                try:
                    account = self.get_account(email)
                except ValueError:
                    pass
                else:
                    invited.add(account["email"])
            saver["invited"] = sorted(invited)
            saver["members"] = [self.current_user["email"]]
        self.see_other("group", saver.doc["_id"])


class GroupEdit(GroupMixin, RequestHandler):
    "Edit group."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_group(iuid)
        self.check_editable(group)
        self.render("group/edit.html", group=group)

    @tornado.web.authenticated
    def post(self, iuid):
        group = self.get_group(iuid)
        self.check_editable(group)
        try:
            with GroupSaver(doc=group, rqh=self) as saver:
                old_members = set(group["members"])
                old_invited = set(group["invited"])
                saver["name"] = self.get_argument("name", "") or "[no name]"
                owner = self.get_account(self.get_argument("owner"))
                if owner["email"] not in old_members:
                    raise ValueError("new owner not among current members")
                saver["owner"] = owner["email"]
                members = set()
                invited = set()
                value = self.get_argument("members", "").replace(",", " ").strip()
                for email in value.split():
                    account = self.get_account(email)
                    if account["email"] in old_members:
                        members.add(account["email"])
                    else:
                        invited.add(account["email"])
                    if account["email"] in old_invited:
                        invited.add(account["email"])
                members.add(owner["email"])
                saver["members"] = sorted(members)
                saver["invited"] = sorted(invited)
        except ValueError as error:
            self.see_other("group", saver.doc["_id"], error=error)
        else:
            self.see_other("group", saver.doc["_id"])


class GroupLogs(GroupMixin, RequestHandler):
    "Display group log entries."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_group(iuid)
        try:
            self.check_readable(group)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        self.render(
            "logs.html",
            title=f"Logs for group {group['name']}",
            logs=self.get_logs(group["_id"]),
        )


class GroupAccept(GroupMixin, RequestHandler):
    "Accept group invitation. Only the user himself can do this."

    @tornado.web.authenticated
    def post(self, iuid):
        group = self.get_group(iuid)
        with GroupSaver(doc=group, rqh=self) as saver:
            invited = set(group["invited"])
            try:
                invited.remove(self.current_user["email"])
            except KeyError:
                self.see_other(
                    "account", self.current_user["email"], error="You are not invited."
                )
            members = set(group["members"])
            members.add(self.current_user["email"])
            saver["invited"] = sorted(invited)
            saver["members"] = sorted(members)
        self.see_other("account", self.current_user["email"])


class GroupDecline(GroupMixin, RequestHandler):
    "Decline group invitation or leave. Only the user himself can do this."

    @tornado.web.authenticated
    def post(self, iuid):
        group = self.get_group(iuid)
        with GroupSaver(doc=group, rqh=self) as saver:
            invited = set(group["invited"])
            invited.discard(self.current_user["email"])
            saver["invited"] = sorted(invited)
            if self.current_user["email"] != group["owner"]:
                members = set(group["members"])
                members.discard(self.current_user["email"])
                saver["members"] = sorted(members)
        self.see_other("account", self.current_user["email"])


class Groups(RequestHandler):
    "List all groups."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        view = self.db.view(
            "group", "modified", descending=True, reduce=False, include_docs=True
        )
        groups = [r.doc for r in view]
        self.render("group/list.html", groups=groups)
