"An order may have reports attached, which should got through a workflow for approval."

# XXX Working!

### Real example: https://ngisweden.scilifelab.se/orders/order/5152fb14a8f0466bb1fdf95c6603a542/report

import tornado.web

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler, ApiV1Mixin


class ReportSaver(saver.Saver):
    doctype = constants.REPORT


class ReportMixin:
    "Mixin for various useful methods."

    def get_report(self, iuid):
        """Get the report for the IUID.
        Raise ValueError if no such report."""
        try:  # Next try report doc IUID.
            return self.get_entity(iuid, doctype=constants.REPORT)
        except tornado.web.HTTPError:
            raise ValueError("Sorry, no such report")

    def allow_read(self, report):
        "Is the report readable by the current user?"
        if self.is_owner(report):
            return True
        if self.am_staff():
            return True
        if self.is_colleague(report["owner"]):
            return True
        return False

    def check_readable(self, report):
        "Check if current user may read the report."
        if self.allow_read(report):
            return
        raise ValueError("You may not read the report.")

    def allow_edit(self, report):
        "Is the report editable by the current user?"
        if self.am_admin():
            return True
        status = settings["REPORT_STATUSES_LOOKUP"][report["status"]]
        edit = status.get("edit", [])
        if self.am_staff() and constants.STAFF in edit:
            return True
        if self.is_owner(report) and constants.USER in edit:
            return True
        return False

    def check_editable(self, report):
        "Check if current user may edit the report."
        if self.allow_edit(report):
            return
        raise ValueError("You may not edit the " + utils.terminology("report"))


class ReportCreate(RequestHandler):
    "Create a new report for an report."

    @tornado.web.authenticated
    def post(self):
        try:
            self.check_creation_enabled()
            form = self.get_form(self.get_argument("form"), check=True)
            with ReportSaver(rqh=self) as saver:
                saver.create(form)
                saver.autopopulate()
                saver.check_fields_validity()
        except ValueError as msg:
            self.see_other("home", error=str(msg))
        else:
            self.see_other("report_edit", saver.doc["_id"])


class Report(RequestHandler):
    "Display a report for an report, or delete it."

    @tornado.web.authenticated
    def get(self, iuid):
        raise NotImplementedError


class ReportLogs(ReportMixin, RequestHandler):
    "Report log entries display."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        try:
            self.check_readable(report)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        title = "Logs for {0} '{1}'".format(
            utils.terminology("report"), report["title"] or "[no title]"
        )
        self.render(
            "logs.html", title=title, entity=report, logs=self.get_logs(report["_id"])
        )


class ReportEdit(RequestHandler):
    "Edit a report for an order."

    @tornado.web.authenticated
    def post(self, iuid):
        report = self.get_report(iuid)
        try:
            self.check_editable(report)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        raise NotImplementedError
