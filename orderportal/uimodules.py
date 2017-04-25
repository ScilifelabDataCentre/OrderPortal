"UI modules for tornado."

from __future__ import print_function, absolute_import

import markdown
import tornado.web
from tornado.escape import xhtml_escape as escape

from . import constants
from . import settings
from . import utils


ICON_TEMPLATE = """<img src="{url}" class="icon" alt="{alt}" title="{title}">"""


class Icon(tornado.web.UIModule):
    "HTML for an icon, optionally labelled with a title."

    def render(self, name, title=None, label=False):
        if not name:
            name = 'unknown'
        elif not isinstance(name, basestring):
            name = name[constants.DOCTYPE]
        # Order status icons are located in the site directory,
        # since they depend on the setup.
        if name in settings['ORDER_STATUSES_LOOKUP']:
            url = self.handler.reverse_url('site', name + '.png')
        else:
            url = self.handler.static_url(name + '.png')
        name = name.capitalize()
        title = utils.terminology(title or name)
        value = ICON_TEMPLATE.format(url=url, alt=name, title=title)
        if label:
            value = '<span class="nobr">{0} {1}</span>'.format(value, title)
        return value


class ContentType(tornado.web.UIModule):
    "HTML for an entity type icon."

    def render(self, content_type):
        url = self.handler.static_url(
            constants.CONTENT_TYPE_ICONS.get(
                content_type, constants.DEFAULT_CONTENT_TYPE_ICON))
        return ICON_TEMPLATE.format(url=url,
                                    alt=content_type,
                                    title=content_type)


class Entity(tornado.web.UIModule):
    "HTML for a link to an entity, optionally with an icon."

    def render(self, entity, icon=True):
        doctype = entity[constants.DOCTYPE]
        assert doctype in constants.ENTITIES
        if doctype == constants.ORDER:
            icon_url = self.handler.static_url('order.png')
            title = entity.get('identifier') or (entity['_id'][:6] + '...')
            alt = 'order'
            url = self.handler.order_reverse_url(entity)
        elif doctype == constants.ACCOUNT:
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
            alt = doctype
            url = self.handler.reverse_url('file_meta', entity['name'])
        else:
            icon_url = self.handler.static_url(doctype + '.png')
            iuid = entity['_id']
            title = entity.get('path') or entity.get('title') or \
                entity.get('name') or iuid
            alt = doctype.capitalize()
            try:
                url = self.handler.reverse_url(doctype, iuid)
            except KeyError, msg:
                raise KeyError(str(msg) + ':', doctype)
        if icon:
            icon = ICON_TEMPLATE.format(url=icon_url, alt=alt, title=alt)
            return u"""<a href="{url}">{icon} {title}</a>""".format(
                url=url, icon=icon, title=title)
        else:
            return u"""<a href="{url}">{title}</a>""".format(
                url=url, title=title)


class Address(tornado.web.UIModule):
    "Format user account address."

    def render(self, address):
        result = []
        for key in ['address', 'postal_code', 'city', 'country']:
            value = address.get(key)
            if value:
                result.append(value)
        return '\n'.join(result)


class Markdown(tornado.web.UIModule):
    "Process the text as Markdown."

    def render(self, text, safe=False):
        if not safe:
            text = escape(text or '')
        return markdown.markdown(text or '', output_format='html5')


class Text(tornado.web.UIModule):
    "Fetch text object from the database, process it, and output."

    def render(self, name, default=None):
        try:
            doc = self.handler.get_entity_view('text/name', name)
            text = doc['text']
        except (tornado.web.HTTPError, KeyError):
            text = default or u"<i>No text for '{0}'.</i>".format(name)
        return markdown.markdown(text, output_format='html5')


class Help(tornado.web.UIModule):
    """Fetch text object from the database, process it,
    and show in a collapsible div.
    """

    def render(self, name, default=None):
        try:
            doc = self.handler.get_entity_view('text/name', name)
            text = doc['text']
        except (tornado.web.HTTPError, KeyError):
            text = default or u"<i>No text for '{0}'.</i>".format(name)
        html = markdown.markdown(text, output_format='html5')
        return u"""<a class="glyphicon glyphicon-info-sign"
title="Help information" data-toggle="collapse" href="#{id}"></a>
<div id="{id}" class="collapse">{html}</div>
""".format(id=name, html=html)


class Tags(tornado.web.UIModule):
    "Output tags with links to search."

    def render(self, tags):
        result = []
        for tag in tags:
            url = self.handler.reverse_url('search', term=tag)
            result.append('<a href="%s">%s</a>' % (url, tag))
        return ', '.join(result)


class NoneStr(tornado.web.UIModule):
    "Output undef string if value is None, else str(value)."

    def render(self, value, undef=''):
        if value is None:
            return undef
        else:
            return str(value)


class Version(tornado.web.UIModule):
    "Output version string if defined."

    def render(self, doc):
        version = doc.get('version')
        if version is None:
            return ''
        else:
            return "(version %s)" % version
