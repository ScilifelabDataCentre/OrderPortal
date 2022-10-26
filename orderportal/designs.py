"CouchDB design documents (view index definitions)."

import json
import logging

import couchdb2

from . import constants
from . import settings

DESIGNS = dict(
    account=dict(
        all=dict(  # account/all
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.modified, null);
}""",
        ),
        api_key=dict(  # account/api_key
            map="""function(doc) { 
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}"""
        ),
        email=dict(  # account/email
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}"""
        ),
        role=dict(  # account/role
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}"""
        ),
        status=dict(  # account/status
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}"""
        ),
        university=dict(  # account/university
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}"""
        ),
    ),
    event=dict(  # event/date
        date=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.date, doc.title);
}"""
        )
    ),
    file=dict(  # file/name
        name=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    emit(doc.name, null);
}"""
        )
    ),
    form=dict(
        all=dict(  # form/all
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, null);
}""",
        ),
        enabled=dict(  # form/enabled
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}"""
        ),
        modified=dict(  # form/modified
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, doc.title);
}"""
        ),
    ),
    group=dict(
        invited=dict(  # group/invited
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.invited.length; i++) {
	emit(doc.invited[i], doc.name);
    };
}"""
        ),
        member=dict(  # group/member
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.members.length; i++) {
	emit(doc.members[i], doc.name);
    };
}"""
        ),
        modified=dict(  # group/modified
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, 1);
}""",
        ),
        owner=dict(  # group/owner
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.owner, doc.name);
}"""
        ),
    ),
    info=dict(
        menu=dict(  # info/menu
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    if (doc.menu) emit(doc.menu, [doc.name, doc.title]);
}"""
        ),
        name=dict(  # info/name
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    emit(doc.name, null);
}"""
        ),
    ),
    log=dict(
        account=dict(  # log/account
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.account) return;
    emit([doc.account, doc.modified], null);
}"""
        ),
        entity=dict(  # log/entity
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}"""
        ),
        login_failure=dict(  # log/login_failure
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}"""
        ),
    ),
    message=dict(
        recipient=dict(  # message/recipient
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], 1);
    };
}""",
        )
    ),
    meta=dict(
        id=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}"""  # meta/id
        )
    ),
    news=dict(  # news/modified
        modified=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'news') return;
    emit(doc.modified, null);
}"""
        )
    ),
    order=dict(
        form=dict(  # order/form
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}""",
        ),
        identifier=dict(  # order/identifier
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}"""
        ),
        keyword=dict(  # order/keyword; see 'fix_design_documents'!
            map="""function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {{
        if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    }});
}};
var lint = {lint};
"""
        ),
        modified=dict(  # order/modified
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
}"""
        ),
        owner=dict(  # order/owner
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}""",
        ),
        status=dict(  # order/status
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}""",
        ),
        tag=dict(  # order/tag
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.tags) return;
    doc.tags.forEach(function(tag) {
	emit(tag.toLowerCase(), doc.title);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.title);
	};
    });
}"""
        ),
        year_submitted=dict(  # order/year_submitted
            reduce="_count",
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.history.submitted) return;
    emit(doc.history.submitted.split('-')[0], 1);
}""",
        ),
    ),
    text=dict(  # text/map
        name=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, doc.modified);
}"""
        )
    ),
)


# This will be added to DESIGNS as 'order/fields'. See 'fix_design_documents'.
# Double {{ and }} are converted to single such by '.format'.
ORDERS_SEARCH_FIELDS_MAP = """function(doc) {{
  if (doc.orderportal_doctype !== 'order') return;
  var value = doc.fields.{fieldid};
  if (!value) return;
  var type = typeof(value);
  if (type === 'string') {{
    var words = value.replace(/[{delims_lint}]/g, " ").toLowerCase().split(/\s+/);
  }} else if (type === 'number') {{
    var words = [value.toString()];
  }} else {{
    var words = value;
  }};
  if (words.length) {{
    words.forEach(function(word) {{
      if (word.length > 2 && !lint[word]) emit(word, null);
    }});
  }};
}};
var lint = {lint};"""


def load_design_documents(db):
    "Load the design documents (view index definitions)."
    fixup_design_documents()
    for designname, views in DESIGNS.items():
        if db.put_design(designname, {"views": views}, rebuild=True):
            logging.info(f"loaded design {designname}")


def fixup_design_documents():
    """Replace 'lint' and 'delims_lint' in design view function 'order/keyword'.
    Add the order search field design views.
    Done on first call to load_design_documents.
    """
    if "fields" in DESIGNS:
        return
    delims_lint = "".join(settings["ORDERS_SEARCH_DELIMS_LINT"])
    lint = "{%s}" % ", ".join(["'%s': 1" % w for w in settings["ORDERS_SEARCH_LINT"]])
    func = DESIGNS["order"]["keyword"]["map"]
    DESIGNS["order"]["keyword"]["map"] = func.format(delims_lint=delims_lint, lint=lint)
    fields = dict()
    for field in settings["ORDERS_SEARCH_FIELDS"]:
        if not constants.ID_RX.match(field):
            raise ValueError(f"Invalid identifier in search field '{field}'.")
        fields[field] = dict(
            map=ORDERS_SEARCH_FIELDS_MAP.format(
                fieldid=field, delims_lint=delims_lint, lint=lint
            )
        )
    DESIGNS["fields"] = fields
