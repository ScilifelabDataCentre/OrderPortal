"OrderPortal: File pages; uploaded files."

from __future__ import print_function, absolute_import

import logging
import os.path
from cStringIO import StringIO

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.requesthandler import RequestHandler


class FileSaver(saver.Saver):
    doctype = constants.FILE

    def check_name(self, value):
        if not constants.NAME_RX.match(value):
            raise tornado.web.HTTPError(400, reason='invalid file name')
        try:
            doc = self.rqh.get_entity_view('file/name', value)
        except tornado.web.HTTPError:
            pass
        else:
            # Error if same name as file of another doc
            if doc['_id'] != self.doc.get('_id'):
                raise ValueError('file name already exists')

    def set_file(self, infile, name=None):
        self.file = infile
        if name:
            self['name'] = name
        self['size'] = len(infile.body)
        self['content_type'] = infile.content_type or 'application/octet-stream'

    def post_process(self):
        "Save the file as an attachment to the document."
        # No new file uploaded, just skip out.
        if self.file is None: return
        # Using cStringIO here is a kludge.
        # Don't ask me why this was required on one machine, but not another.
        # The problem appeared on a Python 2.6 system, and involved Unicode.
        # But I was unable to isolate it. I tested this in desperation...
        self.db.put_attachment(self.doc,
                               StringIO(self.file.body),
                               filename=self['name'],
                               content_type=self['content_type'])
        

class Files(RequestHandler):
    "List of files page."

    def get(self):
        view = self.db.view('file/name', include_docs=True)
        if self.is_admin():
            files = [r.doc for r in view]
        else:
            files = [r.doc for r in view if not r.doc.get('hidden')]
        files.sort(lambda i,j: cmp(i['modified'], j['modified']), reverse=True)
        self.render('files.html', all_files=files)


class File(RequestHandler):
    "Return the file data."

    def get(self, name):
        self.doc = self.get_entity_view('file/name', name)
        filename = self.doc['_attachments'].keys()[0]
        outfile = self.db.get_attachment(self.doc, filename)
        if outfile is None:
            self.write('')
        else:
            self.write(outfile.read())
            outfile.close()
        self.set_header('Content-Type', self.doc['content_type'])


class FileCreate(RequestHandler):
    "Create a new file page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        self.render('file_create.html')

    @tornado.web.authenticated
    def post(self):
        self.check_admin()
        try:
            with FileSaver(rqh=self) as saver:
                try:
                    infile = self.request.files['file'][0]
                except (KeyError, IndexError):
                    raise ValueError('No file uploaded.')
                name = self.get_argument('name', None) or \
                       os.path.splitext(infile.filename)[0]
                saver.check_name(name)
                saver.set_file(infile, name)
                saver['title'] = self.get_argument('title', None)
                saver['hidden'] = utils.to_bool(self.get_argument('hidden',
                                                                  False))
                saver['description'] = self.get_argument('description', None)
        except ValueError, msg:
            self.see_other('files', error=str(msg))
        else:
            self.see_other('files')


class FileCreateApiV1(FileCreate):
    "Create a new file via a script."

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when script is calling."
        pass


class FileEdit(RequestHandler):
    "Edit or delete a file."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.render('file_edit.html', file=file)

    @tornado.web.authenticated
    def post(self, name):
        self.check_admin()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(name)
            return
        file = self.get_entity_view('file/name', name)
        with FileSaver(doc=file, rqh=self) as saver:
            try:
                infile = self.request.files['file'][0]
            except (KeyError, IndexError):
                # No new file upload, just leave it alone.
                saver.file = None
            else:
                saver.set_file(infile)
            saver['title'] = self.get_argument('title', None)
            saver['hidden'] = utils.to_bool(self.get_argument('hidden', False))
            saver['description'] = self.get_argument('description', None)
        self.see_other('files')

    @tornado.web.authenticated
    def delete(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.delete_logs(file['_id'])
        self.db.delete(file)
        self.see_other('files')


class FileEditApiV1(FileEdit):
    "Edit a file via a script."

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when script is calling."
        pass


class FileDownload(File):
    "Download the file."

    def get(self, name):
        super(FileDownload, self).get(name)
        ext = utils.get_filename_extension(self.doc['content_type'])
        if ext:
            name += ext 
        self.set_header('Content-Disposition',
                        'attachment; filename="{0}"'.format(name))


class FileLogs(RequestHandler):
    "File log entries page."

    @tornado.web.authenticated
    def get(self, name):
        self.check_admin()
        file = self.get_entity_view('file/name', name)
        self.render('logs.html',
                    title="Logs for file '{0}'".format(name),
                    entity=file,
                    logs=self.get_logs(file['_id']))
