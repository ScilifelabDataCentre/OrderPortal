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


class Access(IconMixin, tornado.web.UIModule):
    "HTML for access display, optionally labelled."

    def render(self, entity, label=False):
        if label:
            parts = []
            for mode in constants.ACCESS_MODES:
                category = entity['access'].get(mode, constants.PRIVATE)
                value = self.get_icon(category, label=True)
                parts.append("<th>{}</th><td>{}</td>".format(
                        mode.capitalize(), value))
            rows = ''.join(["<tr>{}</tr>".format(p) for p in parts])
            return """<table class="fields">{}</table>""".format(rows)
        else:
            parts = []
            for mode in constants.ACCESS_MODES:
                category = entity['access'].get(mode, constants.PRIVATE)
                title = "{}: {}".format(mode.capitalize(),category.capitalize())
                value = self.get_icon(category, title=title, label=False)
                parts.append(value)
            return ' '.join(parts)


class Submit(IconMixin, tornado.web.UIModule):
    "HTML for a submit button with an icon, optionally with a different title."

    def render(self, name, title=None, onclick=None, slim=False):
        params = dict(type='submit')
        if onclick:
            params['onclick'] = onclick
        if slim:
            params['class'] = 'slim'
        result = "<button {}>".format(' '.join(['{}="{}"'.format(k,v)
                                                for k,v in params.items()]))
        Name = name.capitalize()
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
        Name = name.capitalize()
        iuid = entity.get('iuid') or entity['_id']
        url = self.handler.static_url(name + '.png')
        title = entity.get('path') or entity.get('name') or \
            entity.get('title') or iuid
        icon = ICON_TEMPLATE.format(url=url, alt=Name, title=title)
        try:
            url = self.handler.reverse_url(name, iuid)
        except KeyError, msg:
            raise KeyError(str(msg) + ':', name)
        return """<a href="{url}">{icon} {title}</a>""".format(
            url=url, icon=icon, title=title)

class ParameterValue(tornado.web.UIModule):
    """HTML for displaying the value of a parameter.
    Show links to data and meta pages of item, if local item.
    """

    LOCAL = """<a href="{meta}"><img src="{metaicon}"> {title}</a>;
<a href="{url}"><img src="{icon}"> [data]</a>"""

    REMOTE = """<a href="{url}"><img src="{icon}"> {url}</a>"""

    def render(self, parameter):
        value = parameter.get('value')
        if value is None:
            return '-'
        elif parameter['type'] == constants.URI['value']:
            display = parameter.get('display', {})
            if 'meta' in display: # Local item
                return self.LOCAL.format(
                        icon=self.handler.static_url('local.png'), 
                        metaicon=self.handler.static_url('item.png'),
                       **display)
            else:               # Remote item, or other data resource
                return self.REMOTE.format(
                    icon=self.handler.static_url('remote.png'),
                    **display)
        else:
            return str(value)
