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
        if status not in constants.ALL_STATUSES:
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
            label = order.get("identifier") or "[no identifier]"
        return f"""<a href="{url}">{label}</a>"""


class AccountLink(tornado.web.UIModule):
    "HTML for a link to an account (email or entity), optionally show name or email."

    def render(self, email=None, account=None, name=False, action_required=False):
        if account:
            email = account["email"]
        elif not email:
            raise ValueError("neither email nor account specified")
        if name:
            title = self.handler.lookup_account_name(email)
        else:
            title = email
        if action_required:
            exclaim = '<span class="glyphicon glyphicon-alert text-danger"></span> '
        else:
            exclaim = ""
        url = self.handler.reverse_url("account", email)
        return f"""<a href="{url}">{exclaim}{title}</a>"""


class GroupLink(tornado.web.UIModule):
    "HTML for link to a group."

    def render(self, group, is_owner=False):
        url = self.handler.reverse_url("group", group["_id"])
        if is_owner:
            return f"""<a href="{url}">{group['name']}</a> (owner)"""
        else:
            return f"""<a href="{url}">{group['name']}</a>"""


class FormLink(tornado.web.UIModule):
    "HTML for a link to a form."

    def render(self, form=None, iuid=None, version=False):
        if form is None:
            form = self.handler.lookup_form(iuid)
        url = self.handler.reverse_url("form", form["_id"])
        if version:
            label = (
                f"{form.get('title') or '[no title]'} ({form.get('version') or '-'})"
            )
        else:
            label = form.get("title") or "[no title]"
        return f"""<a href="{url}">{label}</a>"""


class LogsLink(tornado.web.UIModule):
    "HTML for a link to the logs of an entity."

    def render(self, entity):
        url = self.handler.static_url("logs.png")
        icon = ICON_TEMPLATE.format(url=url, alt="Logs", title="Logs")
        url = self.handler.reverse_url(
            f"{entity['orderportal_doctype']}_logs", entity["_id"]
        )
        return f"""<a href="{url}">{icon} Logs</a>"""


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
        return f"<pre>{json.dumps(data, indent=2)}</pre>"


class Tags(tornado.web.UIModule):
    "Output tags with links to search."

    def render(self, tags):
        result = []
        for tag in tags:
            url = self.handler.reverse_url("search", term=tag)
            result.append(f'<a href="{url}">{tag}</a>')
        return ", ".join(result) or "-"


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
        return hg.render(hg.PRE("\n".join(lines)), {})


class TableField(tornado.web.UIModule):
    """Display the field table.
    This is used in only one place, so should really be included in-line.
    However, that turned out to be rather complicated, so let's keep this.
    """

    def render(self, field, value):
        header = hg.TR(hg.TH())
        for coldef in field["table"]:
            column = utils.parse_field_table_column(coldef)
            title = column["identifier"]
            if column["type"] in (constants.INT, constants.FLOAT):
                title += f" ({column['type']})"
            header.append(hg.TH(title))
        rows = []
        if value:
            for i, valuerow in enumerate(value):
                rows.append(hg.TR(hg.TD(str(i + 1), _class="number")))
                for cell in valuerow:
                    if cell is None:
                        rows[-1].append(hg.TD())
                    else:
                        rows[-1].append(hg.TD(str(cell)))
        return hg.render(
            hg.TABLE(
                hg.THEAD(header),
                hg.TBODY(*rows),
                _class="table table-bordered table-condensed",
            ),
            {},
        )


class TableFieldEdit(tornado.web.UIModule):
    """Display the field table for editing. XXX New version, as yet unused.
    This is used in only one place, so should really be included in-line.
    However, that turned out to be rather complicated, so let's keep this.
    """

    def render(self, field, value):
        tableid = f"_table_{field['identifier']}"
        th = hg.TH()
        header = hg.TR(th)
        columns = []
        for coldef in field["table"]:
            column = utils.parse_field_table_column(coldef)
            columns.append(column)
            title = column["identifier"]
            if column["type"] in (constants.INT, constants.FLOAT):
                title += f" ({column['type']})"
            header.append(hg.TH(title))
        rows = []
        if value:
            for i, row in enumerate(value):
                rows.append(self.create_row(tableid, columns, i, row))
        for i in range(len(rows), len(rows) + constants.FIELD_TABLE_ADD_N_ROWS):
            rows.append(self.create_row(tableid, columns, i, []))
        kwargs = dict(id=tableid, _class="table table-bordered table-condensed")
        if len(field["table"]) > 5:
            width = 180 * len(field["table"])
            kwargs[
                "style"
            ] = f"margin-bottom: 0; max-width: {width}px; width: {width}px;"
        else:
            kwargs["style"] = f"margin-bottom: 0;"
        th.append(hg.INPUT(type="hidden", name=f"{tableid}_count", value=len(rows)))
        return hg.render(hg.TABLE(hg.THEAD(header), hg.TBODY(*rows), **kwargs), {})

    def create_row(self, tableid, columns, i, row):
        "Return a new row for the table."
        rowid = f"{tableid}_{i}"
        result = hg.TR(id=rowid)
        result.append(hg.TD(str(i + 1), _class="table-input-row-0"))
        for j, cell in enumerate(columns):
            try:
                cell = row[j]
                if cell is None:
                    cell = ""
            except IndexError:
                cell = ""
            name = f"{tableid}_{i}_{j}"
            coltype = columns[j]["type"]
            if coltype == constants.SELECT:
                input_field = hg.SELECT(name=name, _class="form-control")
                for option in columns[j]["options"]:
                    if option == cell:
                        input_field.append(hg.OPTION(option, selected=True))
                    else:
                        input_field.append(hg.OPTION(option))
            elif coltype == constants.INT:
                input_field = hg.INPUT(
                    type="number", step=1, _class="form-control", name=name, value=cell
                )
            elif coltype == constants.FLOAT:
                input_field = hg.INPUT(
                    type="number",
                    name=name,
                    _class="form-control",
                    step=constants.FLOAT_STEP,
                    value=cell,
                )
            elif coltype == constants.DATE:
                input_field = hg.INPUT(
                    type="text", name=name, _class="form-control datepicker", value=cell
                )
            else:  # Input type for all other types: text
                input_field = hg.INPUT(
                    type="text", name=name, _class="form-control", value=cell
                )
            result.append(hg.TD(input_field))
        return result
