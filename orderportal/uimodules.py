" OrderPortal: UI modules. "

from __future__ import unicode_literals, print_function, absolute_import

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


class Submit(IconMixin, tornado.web.UIModule):
    "HTML for a submit button with an icon, optionally with a different title."

    def render(self, name, title=None, slim=False, confirm=False, disabled=False):
        params = dict(type='submit')
        Name = name.capitalize()
        if confirm:
            text = "return confirm('{} cannot be undone; really {}?');".format(
                Name, name)
            params['onclick'] = text
        if slim:
            params['class'] = 'slim'
        if disabled:
            params['disabled'] = 'disabled'
        result = "<button {}>".format(' '.join(['{}="{}"'.format(k,v)
                                                for k,v in params.items()]))
        result += """<img src="{url}" alt="{name}" title="{name}">""".format(
            url=self.handler.static_url(name + '.png'),
            name=Name)
        result += ' ' + (title or Name)
        result += '</button>'
        return result


class Entity(tornado.web.UIModule):
    "HTML for a link to an entity with an icon."

    def render(self, entity):
        name = entity[constants.DOCTYPE]
        assert name in constants.ENTITIES
        if name == constants.USER:
            icon_url = self.handler.static_url(entity['role'] + '.png')
            title = entity['email']
            alt = entity['role']
            url = self.handler.reverse_url(name, entity['email'])
        elif name == constants.PAGE:
            icon_url = self.handler.static_url(name + '.png')
            title = entity.get('title') or entity['name']
            alt = name
            url = self.handler.reverse_url(name, entity['name'])
        else:
            icon_url = self.handler.static_url(name + '.png')
            iuid = entity.get('iuid') or entity['_id']
            title = entity.get('path') or entity.get('title') or iuid
            alt = name.capitalize()
            try:
                url = self.handler.reverse_url(name, iuid)
            except KeyError, msg:
                raise KeyError(str(msg) + ':', name)
        icon = ICON_TEMPLATE.format(url=icon_url, alt=alt, title=alt)
        return """<a href="{url}">{icon} {title}</a>""".format(
            url=url, icon=icon, title=title)


class Text(tornado.web.UIModule):
    "Fetch Markdown text from the database, process it, and output."

    def render(self, name):
        try:
            doc = self.handler.get_entity_view('text/name', name)
        except tornado.web.HTTPError:
            return "<i>No text '{}' defined.</i>".format(name)
        return markdown.markdown(doc['markdown'], output_format='html5')


class OrderFieldsDisplay(tornado.web.UIModule):
    "HTML displaying the fields of an order."

    def render(self, order, fields):
        rows = []
        for field in fields:
            pass # XXX
