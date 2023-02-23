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

    def render(self, name, title=None, label=False):
        if not name:
            name = "undefined"
        elif not isinstance(name, str):
            name = name[constants.DOCTYPE]
        # Order status icons have been moved to the generic 'static' directory.
        url = self.handler.static_url(name + ".png")
        name = name.capitalize()
        title = utils.terminology(title or name)
        value = ICON_TEMPLATE.format(url=url, alt=name, title=title)
        if label:
            value = f"""<span class="nobr">{value} {title}</span>"""
        return value


class ContentType(tornado.web.UIModule):
    "HTML for a content MIME type icon."

    def render(self, content_type):
        url = self.handler.static_url(
            constants.CONTENT_TYPE_ICONS.get(
                content_type, constants.DEFAULT_CONTENT_TYPE_ICON
            )
        )
        return ICON_TEMPLATE.format(url=url, alt=content_type, title=content_type)


class Entity(tornado.web.UIModule):
    "HTML for a link to an entity, optionally with an icon."

    def render(self, entity, icon=True):
        doctype = entity[constants.DOCTYPE]
        assert doctype in constants.ENTITIES
        if doctype == constants.ORDER:
            icon_url = self.handler.static_url("order.png")
            title = entity.get("identifier") or (entity["_id"][:6] + "...")
            alt = "order"
            url = self.handler.order_reverse_url(entity)
        elif doctype == constants.ACCOUNT:
            icon_url = self.handler.static_url("account.png")
            title = entity["email"]
            alt = entity["role"]
            url = self.handler.reverse_url(doctype, entity["email"])
        elif doctype == constants.INFO:
            icon_url = self.handler.static_url("info.png")
            title = entity.get("title") or entity["name"]
            alt = doctype
            url = self.handler.reverse_url("info", entity["name"])
        else:
            icon_url = self.handler.static_url(doctype + ".png")
            iuid = entity["_id"]
            title = (
                entity.get("path") or entity.get("title") or entity.get("name") or iuid
            )
            alt = doctype.capitalize()
            try:
                url = self.handler.reverse_url(doctype, iuid)
            except KeyError as error:
                raise KeyError(f"{error}: {doctype}")
        if icon and icon_url:
            icon = ICON_TEMPLATE.format(url=icon_url, alt=alt, title=alt)
            return f"""<a href="{url}">{icon} {title}</a>"""
        else:
            return f"""<a href="{url}">{title}</a>"""


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
            a = hg.A(hg.SPAN(_class="glyphicon glyphicon-edit"), " Edit",
                     href=self.handler.reverse_url("text_edit", name, origin=origin),
                     _class="btn btn-primary btn-xs", role="button")
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
    "Output undef string if value is None, else str(value)."

    def render(self, value, undef="", list_delimiter=None):
        if value is None:
            return undef
        elif isinstance(value, list):
            if list_delimiter:
                return list_delimiter.join(value)
        return str(value)


class Version(tornado.web.UIModule):
    "Output version string if defined."

    def render(self, doc):
        version = doc.get("version")
        if version is None:
            return ""
        else:
            return f"({version})"


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
        div = hg.DIV(
            hg.BUTTON(
                hg.SPAN(_class="glyphicon glyphicon-remove"),
                " Cancel",
                type="submit",
                _class="btn btn-default btn-block"
            ),
            _class="form-group")
        form = hg.FORM(div, action=url, method="GET", role="form")
        return hg.render(form, {})
