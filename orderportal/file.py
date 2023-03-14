"File (a.k.a document) pages; uploaded files."

import os.path

import couchdb2
import tornado.web

import orderportal
from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class FileSaver(saver.Saver):
    doctype = constants.FILE

    def check_name(self, value):
        if not constants.NAME_RX.match(value):
            raise tornado.web.HTTPError(400, reason="invalid file name")
        try:
            doc = self.handler.get_entity_view("file", "name", value)
        except tornado.web.HTTPError:
            pass
        else:
            # Error if same name as file of another doc
            if doc["_id"] != self.doc.get("_id"):
                raise ValueError("file name already exists")

    def set_file(self, infile, name=None):
        self.file = infile
        if name:
            self["name"] = name
        self["size"] = len(self.file.body)
        self["content_type"] = infile.content_type or "application/octet-stream"

    def post_process(self):
        "Save the file as an attachment to the document."
        # No new file uploaded, just skip out.
        if self.file is None:
            return
        self.db.put_attachment(
            self.doc,
            self.file.body,
            filename=self["name"],
            content_type=self["content_type"],
        )


class Files(RequestHandler):
    "List of files page."

    def get(self):
        files = [r.doc for r in self.db.view("file", "name", include_docs=True)]
        files.sort(key=lambda i: i["modified"], reverse=True)
        self.render("file/list.html", files=files)


class File(RequestHandler):
    "Return the file data."

    def get(self, name):
        try:
            self.doc = self.get_entity_view("file", "name", name)
            filename = list(self.doc["_attachments"].keys())[0]
            outfile = self.db.get_attachment(self.doc, filename)
        except (tornado.web.HTTPError, IndexError, couchdb2.NotFoundError):
            self.see_other("home", error="Sorry, no such file.")
            return
        if outfile is None:
            self.write("")
        else:
            self.write(outfile.read())
            outfile.close()
        if self.doc["content_type"]:
            self.set_header("Content-Type", self.doc["content_type"])


class FileDownload(File):
    "Download the file."

    def get(self, name):
        super().get(name)
        ext = utils.get_filename_extension(self.doc["content_type"])
        if ext:
            name += ext
        self.set_header("Content-Disposition", f'attachment; filename="{name}"')


class FileCreate(RequestHandler):
    "Create a new file page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render("file/create.html")

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        try:
            with FileSaver(handler=self) as saver:
                try:
                    infile = self.request.files["file"][0]
                except (KeyError, IndexError):
                    raise ValueError("No file uploaded.")
                name = (
                    self.get_argument("name", None)
                    or os.path.splitext(infile.filename)[0]
                )
                saver.check_name(name)
                saver.set_file(infile, name)
                saver["title"] = self.get_argument("title", None)
                saver["hidden"] = utils.to_bool(self.get_argument("hidden", False))
                saver["description"] = self.get_argument("description", None)
        except ValueError as error:
            self.see_other("files", error=error)
        else:
            self.see_other("files")


class FileEdit(RequestHandler):
    "Edit or delete a file."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        file = self.get_entity_view("file", "name", name)
        self.render("file/edit.html", file=file)

    @tornado.web.authenticated
    def post(self, name):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(name)
            return
        self.check_admin()
        file = self.get_entity_view("file", "name", name)
        with FileSaver(doc=file, handler=self) as saver:
            try:
                infile = self.request.files["file"][0]
            except (KeyError, IndexError):
                # No new file upload, just leave it alone.
                saver.file = None
            else:
                saver.set_file(infile)
            saver["title"] = self.get_argument("title", None)
            saver["hidden"] = utils.to_bool(self.get_argument("hidden", False))
            saver["description"] = self.get_argument("description", None)
        self.see_other("files")

    @tornado.web.authenticated
    def delete(self, name):
        self.check_admin()
        file = self.get_entity_view("file", "name", name)
        self.delete_logs(file["_id"])
        self.db.delete(file)
        self.see_other("files")


class FileEditApiV1(FileEdit):
    "API for editing a file."

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when script is calling."
        pass


class FileLogs(RequestHandler):
    "File log entries page."

    def get(self, iuid):
        file = self.get_entity(iuid, doctype=constants.FILE)
        self.render(
            "logs.html",
            title=f"Logs file '{file['name']}'",
            logs=self.get_logs(file["_id"]),
        )
