" OrderPortal: UI modules. "

from __future__ import unicode_literals, print_function, absolute_import

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

    def render(self, entity, name=None):
        if not name:
            name = entity[constants.DOCTYPE]
        assert name in constants.ENTITIES
        iuid = entity.get('iuid') or entity['_id']
        if name == 'user':
            url = self.handler.static_url(entity['role'] + '.png')
            title = entity['email']
            alt = entity['role']
        else:
            url = self.handler.static_url(name + '.png')
            title = entity.get('path') or entity.get('title') or iuid
            alt = name.capitalize()
        icon = ICON_TEMPLATE.format(url=url, alt=alt, title=alt)
        if name == 'user':
            url = self.handler.reverse_url(name, entity['email'])
        else:
            try:
                url = self.handler.reverse_url(name, iuid)
            except KeyError, msg:
                raise KeyError(str(msg) + ':', name)
        return """<a href="{url}">{icon} {title}</a>""".format(
            url=url, icon=icon, title=title)


class OrderFieldsDisplay(tornado.web.UIModule):
    "HTML displaying the fields of an order."

    def render(self, order, fields):
        rows = []
        for field in fields:
            pass # XXX
