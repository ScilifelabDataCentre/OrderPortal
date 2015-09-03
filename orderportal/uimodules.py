" OrderPortal: UI modules. "

from __future__ import print_function, absolute_import

import os.path

import couchdb
import markdown
import tornado.web

from . import constants


ICON_TEMPLATE = """<img src="{url}" class="icon" alt="{alt}" title="{title}">"""


class IconMixin(object):

    def get_icon(self, name, title=None, label=False):
        url = self.handler.static_url(name + '.png')
        alt = name.capitalize()
        title = title or alt
        value = ICON_TEMPLATE.format(url=url, alt=alt, title=title)
        if label:
            value += """ <span class="icon">{}</span>""".format(title)
        return value


class Icon(IconMixin, tornado.web.UIModule):
    "HTML for an icon, optionally labelled with a title."

    def render(self, name, title=None, label=False):
        if not name:
            name = 'unknown'
        elif not isinstance(name, basestring):
            name = name[constants.DOCTYPE]
        return self.get_icon(name, title=title, label=label)


class Entity(tornado.web.UIModule):
    "HTML for a link to an entity with an icon."

    def render(self, entity):
        doctype = entity[constants.DOCTYPE]
        assert doctype in constants.ENTITIES
        if doctype == constants.ACCOUNT:
            icon_url = self.handler.static_url(entity['role'] + '.png')
            title = entity['email']
            alt = entity['role']
            url = self.handler.reverse_url(doctype, entity['email'])
        elif doctype == constants.INFO:
            icon_url = self.handler.static_url('info.png')
            title = entity.get('title') or entity['name']
            alt = doctype
            url = self.handler.reverse_url('info', entity['name'])
        elif doctype == constants.FILE:
            icon_url = self.handler.static_url('file.png')
            title = entity['name']
            alt = title
            url = self.handler.reverse_url('file_meta', entity['name'])
        else:
            icon_url = self.handler.static_url(doctype + '.png')
            iuid = entity.get('iuid') or entity['_id']
            title = entity.get('path') or entity.get('title') or iuid
            alt = doctype.capitalize()
            try:
                url = self.handler.reverse_url(doctype, iuid)
            except KeyError, msg:
                raise KeyError(str(msg) + ':', doctype)
        icon = ICON_TEMPLATE.format(url=icon_url, alt=alt, title=alt)
        return """<a href="{url}">{icon} {title}</a>""".format(
            url=url, icon=icon, title=title)


class Markdown(tornado.web.UIModule):
    "Process the text as Markdown."

    def render(self, text):
        return markdown.markdown(text or '', output_format='html5')


class Text(tornado.web.UIModule):
    "Fetch text object from the database, process it, and output."

    def render(self, name, default=None):
        try:
            doc = self.handler.get_entity_view('text/name', name)
            text = doc['text']
        except (tornado.web.HTTPError, KeyError):
            text = default or ''
        return markdown.markdown(text, output_format='html5')
