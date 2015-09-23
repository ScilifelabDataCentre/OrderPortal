"OrderPortal: Group pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class GroupSaver(saver.Saver):
    doctype = constants.GROUP


class GroupMixin(object):

    def check_readable(self, group):
        "Check if current user may read the group."
        if self.is_owner(group): return
        if self.current_user['email'] in group['members']: return
        if self.is_staff(): return
        raise tornado.web.HTTPError(403, reason='you may not read the group')

    def is_editable(self, group):
        "Is the group editable by the current user?"
        if self.is_admin(): return True
        if self.is_owner(group): return True
        return False

    def check_editable(self, group):
        "Check if current user may edit the group."
        if not self.is_editable(group):
            raise tornado.web.HTTPError(403,
                                        reason='you may not edit the group')


class Group(GroupMixin, RequestHandler):
    "Group page."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_entity(iuid, doctype=constants.GROUP)
        self.check_readable(group)
        self.render('group.html',
                    group=group,
                    is_editable=self.is_editable(group))


class GroupCreate(RequestHandler):
    "Create group page."

    @tornado.web.authenticated
    def get(self):
        self.render('group_create.html')

    @tornado.web.authenticated
    def post(self):
        with GroupSaver(rqh=self) as saver:
            saver['name'] = self.get_argument('name', '') or '[no name]'
            saver['owner'] = self.current_user['email']
            members = set()
            for member in self.get_argument('members', '').strip().split('\n'):
                try:
                    members.add(self.get_account(member)['email'])
                except tornado.web.HTTPError:
                    pass
            members.add(self.current_user['email'])
            saver['members'] = sorted(members)
        self.see_other('group', saver.doc['_id'])


class GroupEdit(GroupMixin, RequestHandler):
    "Edit group page."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_entity(iuid, doctype=constants.GROUP)
        self.check_editable(group)
        self.render('group_edit.html', group=group)

    @tornado.web.authenticated
    def post(self):
        group = self.get_entity(iuid, doctype=constants.GROUP)
        self.check_editable(group)
        with GroupSaver(doc=group, rqh=self) as saver:
            saver['name'] = self.get_argument('name', '') or '[no name]'
            owner = self.get_account(self.get_argument('owner'))
            if owner['email'] not in group['members']:
                raise ValueError('new owner not among members')
            saver['owner'] = owner['email']
            members = set()
            for member in self.get_argument('members', '').strip().split('\n'):
                try:
                    members.add(self.get_account(member)['email'])
                except tornado.web.HTTPError:
                    pass
            members.add(owner['email'])
            saver['members'] = sorted(members)
        self.see_other('group', saver.doc['_id'])


class GroupLogs(GroupMixin, RequestHandler):
    "Group log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        group = self.get_entity(iuid, doctype=constants.GROUP)
        self.check_readable(group)
        self.render('logs.html',
                    title="Logs for group '{}'".format(group['name']),
                    entity=group,
                    logs=self.get_logs(group['_id']))
