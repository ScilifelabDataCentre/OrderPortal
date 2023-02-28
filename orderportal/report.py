"An order may have reports attached, which should got through a workflow for approval."

# XXX On-going work

### Real example: https://ngisweden.scilifelab.se/orders/order/5152fb14a8f0466bb1fdf95c6603a542/report

import tornado.web

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler, ApiV1Mixin


class ReportSaver(saver.Saver):
    doctype = constants.REPORT

    def set_status(self, new):
        "Set the new status of the report."
        if self.get("status") == new:
            return
        if new not in constants.REPORT_STATUSES:
            raise ValueError(f"invalid status '{new}'")
        self["status"] = new

    def set_inline(self, content_type):
        "Set the 'inline' flag according to explicit argument, or content type."
        try:
            self["inline"] = utils.to_bool(self.rqh.get_argument("inline"))
        except (tornado.web.MissingArgumentError, ValueError):
            self["inline"] = content_type in (constants.HTML_MIMETYPE, constants.TEXT_MIMETYPE)


class ReportMixin:
    "Mixin access methods."

    def allow_read(self, report):
        "Is the report readable by the current user?"
        if self.am_staff():
            return True
        if report["status"] == constants.PUBLISHED:
            order = self.get_order(report["order"])
            if self.am_owner(order):
                return True
        return False

    def check_readable(self, report):
        "Check if current user may read the report."
        if self.allow_read(report):
            return
        raise ValueError("You may not read the report.")

    def allow_edit(self, report):
        "Is the report editable by the current user?"
        if self.am_staff():
            return True
        return False

    def check_editable(self, report):
        "Check if current user may edit the report."
        if self.allow_edit(report):
            return
        raise ValueError("You may not edit the report.")


class ReportCreate(RequestHandler):
    "Create a new report for an report."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        try:
            order = self.get_order(self.get_argument("order"))
        except ValueError as error:
            self.see_other("home", error=f"Sorry, no such {{ terminology('order') }}.")
        self.render("report/create.html", order=order)

    @tornado.web.authenticated
    def post(self):
        self.check_staff()
        try:
            order = self.get_order(self.get_argument("order"))
        except ValueError as error:
            self.see_other("home", error=f"Sorry, no such {{ terminology('order') }}.")
            return
        try:
            file = self.request.files["report"][0]
        except (KeyError, IndexError):
            self.see_other("order", order["_id"], error="No file to upload given.")
            return
        try:
            with ReportSaver(rqh=self) as saver:
                saver["order"] = order["_id"]
                saver["name"] = file.filename
                saver.set_inline(file.content_type)
                saver.set_status(constants.PREPARATION)
            self.db.put_attachment(
                saver.doc,
                file.body,
                filename=file.filename,
                content_type=file.content_type
            )
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
        else:
            self.see_other("order", order["_id"])


class Report(ReportMixin, RequestHandler):
    "Display or download a report for an report, or delete it."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_readable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        outfile = self.db.get_attachment(report, report["name"])
        content_type = report["_attachments"][report["name"]]["content_type"]
        if report.get("inline"):
            self.render(
                "report/inline.html",
                order=self.get_order(report["order"]),
                report=report,
                content=outfile.read(),
                content_type=content_type,
            )
        else:
            self.write(outfile.read())
            outfile.close()
            self.set_header("Content-Type", content_type)
            self.set_header(
                "Content-Disposition", f'''attachment; filename="{report['name']}"'''
            )

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason="POST only allowed for DELETE.")

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_staff()
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
            return
        order = self.get_order(report["order"])
        self.delete_logs(report["_id"])
        self.db.delete(report)
        self.see_other("order", order["_id"])


class ReportEdit(ReportMixin, RequestHandler):
    "Edit a report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_readable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        self.render(
            "report/edit.html",
            report=report,
            order=self.get_order(report["order"])
        )

    @tornado.web.authenticated
    def post(self, iuid):
        report = self.get_report(iuid)
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        order = self.get_order(report["order"])
        try:
            file = self.request.files["report"][0]
        except (KeyError, IndexError):
            self.see_other("order", order["_id"], error="No file to upload given.")
            return
        try:
            with ReportSaver(doc=report, rqh=self) as saver:
                saver["name"] = file.filename
                saver.set_inline(file.content_type)
            self.db.put_attachment(
                saver.doc,
                file.body,
                filename=file.filename,
                content_type=file.content_type
            )
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
        else:
            self.see_other("order", order["_id"])


class ReportLogs(ReportMixin, RequestHandler):
    "Report log entries display."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_readable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        title = f"Logs for report '{report['name'] or '[no name]'}'"
        self.render("logs.html", title=title, logs=self.get_logs(report["_id"]))
