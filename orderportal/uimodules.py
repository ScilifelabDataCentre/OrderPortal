"UI modules for tornado."

import json
import logging

import htmlgenerator as hg
import tornado.web

from orderportal import constants, settings
from orderportal import utils

ICON_TEMPLATE = """<img src="{url}" class="icon" alt="{alt}" title="{title}">"""


class Icon(tornado.web.UIModule):
    "HTML for an icon, optionally labelled with a title."

    def render(self, name):
        if not name:
            name = "undefined"
        # Order status icons have been moved to the generic 'static' directory.
        url = self.handler.static_url(name + ".png")
        name = utils.terminology(name.capitalize())
        return ICON_TEMPLATE.format(url=url, alt=name, title=name)


class Status(tornado.web.UIModule):
    "HTML for a status; order, account."

    def render(self, status):
        if status not in constants.ORDER_STATUSES:
            status = "undefined"
        # Order status icons are now in the generic 'static' directory.
        url = self.handler.static_url(status + ".png")
        status = status.capitalize()
        icon = ICON_TEMPLATE.format(url=url, alt=status, title=status)
        return f"""<span class="nobr">{icon} {status}</span>"""


class ContentType(tornado.web.UIModule):
    "HTML for a content MIME type icon."

    def render(self, content_type):
        url = self.handler.static_url(
            constants.CONTENT_TYPE_ICONS.get(
                content_type, constants.DEFAULT_CONTENT_TYPE_ICON
            )
        )
        return ICON_TEMPLATE.format(url=url, alt=content_type, title=content_type)


class OrderLink(tornado.web.UIModule):
    "HTML for a link to an order."
    
    def render(self, order, title=False):
        url = self.handler.order_reverse_url(order)
        if title:
            label = f"{order['identifier']} {order['title'] or '[no title]'}"
        else:
            label = order['identifier']
        return f"""<a href="{url}">{label}</a>"""


class AccountLink(tornado.web.UIModule):
    """HTML for a link to an account (email or entity), optionally with an icon,
    and optionally show name and/or email.
    """
    
    def render(self, email=None, account=None, name=False):
        if account:
            email = account["email"]
        elif not email:
            raise ValueError("neither email nor account specified")
        if name:
            title = self.handler.lookup_account_name(email)
        else:
            title = email
        url = self.handler.reverse_url("account", email)
        return f"""<a href="{url}">{title}</a>"""


class GroupLink(tornado.web.UIModule):
    "HTML for link to a group."

    def render(self, group, show_am_owner=False):
        url = self.handler.reverse_url("group", group["_id"])
        if show_am_owner:
            return f"""<a href="{url}">{group['name']}</a> (am owner)"""
        else:
            return f"""<a href="{url}">{group['name']}</a>"""


class FormLink(tornado.web.UIModule):
    "HTML for a link to a form."

    def render(self, form=None, iuid=None, version=False):
        if form is None:
            form = self.handler.lookup_form(iuid)
        url = self.handler.reverse_url("form", form["_id"])
        if version:
            label = f"{form.get('title') or '[no title]'} ({form.get('version') or '-'})"
        else:
            label = form.get('title') or '[no title]'
        return f"""<a href="{url}">{label}</a>"""


class LogsLink(tornado.web.UIModule):
    "HTML for a link to the logs of an entity."

    def render(self, entity):
        url = self.handler.static_url("logs.png")
        icon = ICON_TEMPLATE.format(url=url, alt="Logs", title="Logs")
        url = self.handler.reverse_url(f"{entity['orderportal_doctype']}_logs", entity["_id"])
        return f"""<a href="{url}">{icon} Logs</a>"""


class Markdown(tornado.web.UIModule):
    "Process the text as Markdown."

    def render(self, text, safe=False):
        return utils.markdown2html(text, safe=safe)


class Text(tornado.web.UIModule):
    "Process the display Markdown text message fetched from the settings and output."

    def render(self, name, origin=None):
        try:
            text = settings[constants.DISPLAY][name]["text"]
            if not text:
                raise KeyError
        except KeyError:
            if self.handler.am_admin():
                text = "*No text defined.*"
            else:
                return ""
        if origin and self.handler.am_admin():
            a = hg.A(
                hg.SPAN(_class="glyphicon glyphicon-edit"),
                " Edit",
                href=self.handler.reverse_url("text_edit", name, origin=origin),
                _class="btn btn-primary btn-xs",
                role="button",
            )
            div = hg.DIV(hg.mark_safe(utils.markdown2html(text, safe=True)), a)
            return hg.render(div, {})
        else:
            return utils.markdown2html(text, safe=True)


class Json(tornado.web.UIModule):
    "Display JSON with indent."

    def render(self, data):
        return "<pre>" + json.dumps(data, indent=2) + "</pre>"


class Tags(tornado.web.UIModule):
    "Output tags with links to search."

    def render(self, tags):
        result = []
        for tag in tags:
            url = self.handler.reverse_url("search", term=tag)
            result.append('<a href="%s">%s</a>' % (url, tag))
        return ", ".join(result)


class NoneStr(tornado.web.UIModule):
    "Output undef string if value is None, else str(value); handle lists."

    def render(self, value, undef="", list_delimiter=None):
        if value is None:
            return undef
        elif isinstance(value, list):
            if list_delimiter:
                return list_delimiter.join(value)
        return str(value)


class ShortenedPre(tornado.web.UIModule):
    "Shorten lines to output within <pre> tags."

    def render(self, lines, maxlength=16):
        lines = lines or []
        for pos, line in enumerate(lines):
            if len(line) > maxlength:
                line = line[:maxlength] + "..."
                lines[pos] = line
        return "<pre>%s</pre>" % "\n".join(lines)


class TableRows(tornado.web.UIModule):
    "Display the table rows."

    def render(self, field, value):
        assert field["type"] == constants.TABLE
        result = ["<thead>", "<tr>", "<th></th>"]
        for coldef in field["table"]:
            column = utils.parse_field_table_column(coldef)
            header = column["identifier"]
            if column["type"] in (constants.INT, constants.FLOAT):
                header += " (%s)" % column["type"]
            result.append("<th>%s</th>" % header)
        result.append("</tr>")
        result.append("</thead>")
        result.append("<tbody>")
        if value:
            for i, row in enumerate(value):
                result.append("<tr>")
                result.append('<td class="number">%s</td>' % (i + 1))
                for cell in row:
                    if cell is None:
                        cell = ""
                    result.append("<td>%s</td>" % cell)
                result.append("</tr>")
        result.append("</tbody>")
        return "\n".join(result)


class TableRowsEdit(tornado.web.UIModule):
    "Display the table rows for editing."

    def render(self, field, value):
        assert field["type"] == constants.TABLE
        result = ["<thead>", "<tr>", "<th></th>"]
        columns = []
        for coldef in field["table"]:
            column = utils.parse_field_table_column(coldef)
            columns.append(column)
            header = column["identifier"]
            if column["type"] in (constants.INT, constants.FLOAT):
                header += " (%s)" % column["type"]
            result.append("<th>%s</th>" % header)
        result.append("</tr>")
        result.append("</thead>")
        if value:
            result.append("<tbody>")
            for i, row in enumerate(value):
                rowid = "_table_%s_%s" % (field["identifier"], i)
                result.append('<tr id="%s">' % rowid)
                result.append('<td class="table-input-row-0">%s</td>' % (i + 1))
                for j, cell in enumerate(columns):
                    try:
                        cell = row[j]
                        if cell is None:
                            cell = ""
                    except IndexError:
                        cell = ""
                    result.append("<td>")
                    name = "_table_%s_%s_%s" % (field["identifier"], i, j)
                    coltype = columns[j]["type"]
                    if coltype == constants.SELECT:
                        result.append('<select class="form-control" name="%s">' % name)
                        for option in columns[j]["options"]:
                            if option == cell:
                                result.append("<option selected>%s</option>" % option)
                            else:
                                result.append("<option>%s</option>" % option)
                        result.append("</select>")
                    elif coltype == constants.INT:
                        result.append(
                            '<input type="number" step="1"'
                            ' class="form-control"'
                            ' name="%s" value="%s">' % (name, cell)
                        )
                    elif coltype == constants.FLOAT:
                        result.append(
                            '<input type="number"'
                            ' class="form-control"'
                            ' name="%s" value="%s">' % (name, cell)
                        )
                    elif coltype == constants.DATE:
                        result.append(
                            '<input type="text"'
                            ' class="form-control datepicker"'
                            ' name="%s" value="%s">' % (name, cell)
                        )
                    else:  # Input type for all other types: text
                        result.append(
                            '<input type="text" class="form-control"'
                            ' name="%s" value="%s">' % (name, cell)
                        )
                result.append(
                    "<td>"
                    '<button type="button" class="btn btn-danger"'
                    """ onclick="$('#%s').remove()">Delete"""
                    "</button>"
                    "</td>" % rowid
                )
                result.append("</tr>")
            result.append("</tbody>")
        return "\n".join(result)


class CancelButton(tornado.web.UIModule):
    "Display a standard cancel button."

    def render(self, url):
        a = hg.A(
            hg.SPAN(_class="glyphicon glyphicon-remove"),
            " Cancel",
            href=url,
            _class="btn btn-default btn-block",
        )
        return hg.render(a, {})
