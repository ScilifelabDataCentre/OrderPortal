# Summary 

The OrderPortal system is a web-based portal that allows form-based
submission of information from users to a facility. It was designed
academic service facilities that handle discrete orders or project
proposals, reports, etc, from its researcher users. It has also been
used as a system to gather reports from researchers and research
units.

The OrderPortal system was originally created to satisfy the needs of the
[National Genomics Infrastructure (NGI) Sweden](https://ngisweden.scilifelab.se/ "!"),
which is a service facility for DNA sequencing and genotyping of
samples provided by external researchers. The facility processes the
samples according to the specifications in the order from the
researcher.  The available services are described in the forms for
orders that the facility defines.

The OrderPortal system is not hardcoded for any specific area such as
DNA sequencing. On the contrary, considerable effort has gone into
making sure the design is as general as possible within the scope of
the basic problem it is intended to solve.

Since the system is general in character, the installation of it
requires specific configuration settings to suite your particular
needs.


## Features

* Allow a user (researcher) to register an account, which is enabled
  by the facility staff.
* Allows system administrators to create predefined forms with a
  specific set of input fields.
* Allow the user to specify an order according to one of the predefined forms.
* Allow input from the user of required project data, such as sample sheets.
* Allow the user to submit the order to the facility.
* The facility staff can review, accept or decline an order, depending
  on the configuration set up by system administrators.
* Let the facility staff keep track of review and agreements.
* Allow attaching files to an order.
* Display project status reports.
* Allow keeping track of Key Performance Indicators (KPIs), facilitating
  resource usage reports for the facility.


## Basic concepts

The system is a portal for **orders** (requests, project proposals,
etc) to a single facility from its users. A **user** is a researcher
external to the service facility, and may or may not be the Principal
Investigator (PI) for one or more projects.

An order is created from a template which is called a **form** in the
OrderPortal system. The system administrators must set up and publish
the forms for a researcher to be able to create an order. Each form
defines the fields for data to be input by the researcher.

The OrderPortal system is designed for only one facility, displaying
up to about 8 different order forms. There is no hard limit to the
number of simultaneously published forms, but the current design does
not work well with more than about 8 forms.

If an organization has different facilities requiring different sets
of forms, then it is probably a good idea to set up different
instances of the OrderPortal system, with separate back-end database
instances.

The design of an order form is fairly general; there is nothing that
is hardcoded for specific domains of science. The content of the order
forms consists of a different fields for different types of input
data, with optional constraints on the input data, and optional help
text. The order forms are defined by the system administrators.

A **user account** is defined within each OrderPortal instance. The email
address of the user is the user account identifier. This means that if
a user changes email address, a new account will have to be created.

The system administrators can (and should) customisation the site
logo, title, home page text blocks and the body of email messages sent
by the system. Pages for showing information and documents are under
control of the system administrators.


# Facility

The term facility is used for the organisation providing the service
specified by the order forms. A basic design principle is that one
instance of the OrderPortal system handles one facility. All entities
in the database back-end for the OrderPortal instance belong to one
and only one facility.

There are three reasons for this design choice:

1. Security between facilities. The existence and contents of a
   particular project in one facility must not be visible to the
   administrators or staff of another facility. This is a strict requirement
   for some facilities, and it is easier to implement if the database instance
   for each facility is separate from one another.

2. The styling of an order portal is much easier to implement if each
   facility has its own OrderPortal instance.

3. The introduction, or elimination, of a facility in the overall
   organisation becomes much easier if every instance of the system is
   independent of the other.

One drawback with this design choice is that it complicates the
communication between, and linking of, different but related projects in
different facilities.

Note that there is no entity called `facility` in the OrderPortal system.
It is just a concept behind the design of the system.


# Users

A user is an account in the system. Almost all operation require that
the user is logged in. The email address is the user account identifier.

There are three kinds (=roles) of users:

1. User: An external scientist, who uses the portal to place one or
   more orders, and to follow the progress of their own orders. The
   "customer" of the facility.

2. Staff: Facility staff, who may view all orders, but are not allowed
   to change very much.

3. Admin: System administrators who are allowed to view and edit all
   aspects of the OrderPortal system that can be modified via the web
   interface. This includes processing orders, modifying the order
   fields, and handling user accounts. Often, the project coordinators
   of the facility are designated as system administrators, since they
   will be using the system to keep track of incoming orders
   (projects).

User accounts can be set as disabled, for example if the person leaves
her position, or as a means of blocking invalid use. An account can be
re-enabled. A user account cannot be deleted, since the logs and old
orders contain a link to it.

An external scientist applies for a user account by providing the
relevant information. Such an account is created with a status of
**pending**. The system administrator reviews the pending user account and
enables it if it appears legitimate. The user gets an email about the
account having been enabled and with instructions on how to set the
password for it.


## Access privileges

The user can place orders as soon has she has logged in. By default,
no other users except the admin and staff can view the orders.

A user is allowed to specify which other users will be able to access
to her orders by creating a group to which the other users are
invited. Access can also be granted by a user to other specific users
for an individual order.


# Order

An order is essentially a form with values. Its fields are defined by
the order form ([see below](/documentation#order-form)) it was created from.

An order belongs to one and only one user account.

An order has one and only on status at any time. When the order is
created, it is in status PREPARATION, and while it is in that state,
the user can edit it and save it. An order that is being prepared can
be, but is usually not, inspected by the staff or system
administrators.

An order usually contains at least some fields which require a
value. An order lacking a required value can be saved, but it cannot
be submitted. This allows the user to create and fill in an order
partially and save it. Then, at a later data, she can return to the
order to complete it and then submit it.

When all fields have been given valid values by the user, it becomes
possible to submit it.

An order in status SUBMITTED will be handled by the staff and system
administrators.


## Order status

This is a list of all possible order statuses:

| State       | Semantics                                                     |
|-------------|---------------------------------------------------------------|
| PREPARATION | The order has been created and is being edited by the user.   |
| SUBMITTED   | The order has been submitted by the user for consideration.   |
| REVIEW      | The order is under review.                                    |
| QUEUED      | The order has been queued.                                    |
| WAITING     | The order is waiting.                                         |
| ACCEPTED    | The order has been checked and accepted.                      |
| REJECTED    | The order has been rejected.                                  |
| PROCESSING  | The order is being processed in the lab.                      |
| ACTIVE      | The order is active.                                          |
| ANALYSIS    | The order results are being analysed.                         |
| ONHOLD      | The order is on hold.                                         |
| HALTED      | The work on the order has been halted.                        |
| ABORTED     | The work on the order has been permanently stopped.           |
| TERMINATED  | The order has been terminated.                                |
| CANCELLED   | The order has been cancelled.                                 |
| FINISHED    | The work on the order has finished.                           |
| COMPLETED   | The order has been completed.                                 |
| CLOSED      | All work and other actions for the order have been performed. |
| DELIVERED   | The order results have been delivered.                        |
| INVOICED    | The order has been invoiced.                                  |
| ARCHIVED    | The order has been archived.                                  |
| UNDEFINED   | The order has an undefined or unknown status.                 |

Only the statuses PREPARATION and SUBMITTED are enabled by default. All other
statuses will have to be enabled to become available for use.

Statuses can be enabled by the system administrators.  Once enabled, a
status cannot be disabled. The reason for this is that already
existing orders may be in a specific status, or have a specific status
recorded in its history, and removing such a status would introduce
inconsistencies in the database. The description of the semantic of a
status can be edited by the system administrators.

Transitions between the statuses can be edited by the system
administrators. The only transition enabled by default is the one from
PREPARATION to SUBMITTED.

Typically, enabling statuses and transitions should be done as part of
the configuration and testing phase before the instance is launched
into production. Obviously, this work needs to take into account the
typical workflow of the facility.

Here are some general guidelines:

- It is a good idea to keep the number of enabled statuses at a minimum.
  Since a status that has been enabled cannot be disabled, one should avoid
  cluttering the system with unnecessary statuses.
- Transitions should be set to those that are sensible given the typical workflow.
- Allowing too many transitions can lead to confusion and should be avoided.
- However, setting up transitions can be done freely, since they can be
  removed later without any issue.
- Since transitions can be added and removed at will by the system
  administrators, it is always in principle possible (if cumbersome) to
  'rescue' an order which has been put in an incorrect status.


## Attach files

Files such as agreements, specifications, images, etc, can be attached
to an order. If the form has file input fields, these files will also be
attached to the order.


## Order links

Links to other web pages can be set for orders, allowing users to
navigate to other relevant information systems.  This feature can be
disabled by modifying the order configuration.


## Order tags

Tags (one-word labels) can be attached to orders, for searching purposes.
This feature can be disabled by modifying the order configuration.


## Order log

Each change of an order is logged, and the information "who, when,
what" is stored. The log trace is written by the system automatically
and cannot be edited by any user.


# Order form

The order form fields are fully configurable by the system
administrators via the web interface. The field definitions are
generic, and allow order forms to be designed for a wide variety of
input data.

While an order form is being created and edited, it is upublished, and
users cannot create orders from it. It is possible for the system
administrators to test a form and create a dummy order for it. An
order form can be used only when it has been enabled, which
automatically publishes it on the home page of the OrderPortal
system.

The input fields defined by an order form cannot be substantially
changed after the form has been enabled. Basically only the help texts
of the input fields can be edited. If an order form becomes outdated
it can be disabled; this will remove it from view on the home
page. Its orders, however, will still be accessible for processing. No
new orders can be created from a disabled form. New order forms can be
created by cloning from and older form; this is the most common way of
updating an order form.

The reason for this is that if a form is changed by e.g. removing a
field, or redefining it, then already created orders are in danger of
becoming invalid. It was a design decision to stop this from
happening by disallowing changing a form after it has been enabled.


## Order form fields

The fields of an order form, and by extension the orders created from it,
are of different types, for input of text, number or other kinds of values.
This is defined when a field is created within a form.

The order form allows hierarchical grouping of fields, with dynamic
display according to simple rules. This allows for cases where a
top-level selection of e.g. a specific technology determines which
further input fields are required to be filled in.

The system administrators design the forms by setting up the fields
which determine what the user must fill in for an order. The system
administrators can clone a form in order to make a new variant of
it. Old forms can be disabled, and new forms enabled, as needed.

Once a form has been enabled, its fields cannot be changed, except for
editing the help texts. When an order is created, its fields
definitions are copied from the form. Once an order has been created,
its fields and selected options are effectively frozen, and remain
fixed. Only the values of the fields may be changed, not the
definition of them.

This is a major design limitation of the OrderPortal system, which
must be kept in mind when planning and implementing the content of the
forms. The following routine has been used with good results:

1. For a new form, create and edit the input fields that it defines for an order.
2. Set the version marker for the form, using some reasonable
   convention, such as a version number, or a date.
3. Enable it.
4. When an update of the form is required, make a clone of it.
5. Edit the fields of the clone to make the changes.
6. Set a new version marker, keeping the title of the new form
   unchanged compared to the old. To the users it will look like just
   an updated form, not a new one.
7. Enable the new form.
8. Disable the old form.

Adding a field in a new form requires deciding on the following parameters:

- Field identifier.
- Field data type.
- Is a field value required?
- Field description.
- Value options, if relevant.
- Hierarchy and order, including conditional visibility.
- Visibility to the user; some fields may be visible only to the staff.

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is useful for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

## Field types

The order form field types are:

- **String**: One single line of text, such as a name or a title.
- **Email**: One single email address.
- **Int**: A number that is a whole integer.
- **Float**: A number that may contain fractions.
- **Boolean**: A selection between Yes and No.
- **Url**: One single URL (link address).
- **Select**: A choice of one among a set of text given values.
- **Multiselect**: A choice among a set of text given values, allowing multiple selected values.
- **Text**: A multiline text which may use
  [Markdown formatting](https://www.markdownguide.org/basic-syntax/).
- **Date**: One single date, using ISO format (YYY-MM-DD).
- **Table**: A basic table allowing several columns.
- **File**: An uploaded file which is attached to the order.
- **Group*: A group of a set of other fields. Does not contain a value.


# Info pages

There is a very basic information page subsystem, intended to allow
displaying information about the orders and/or the facility to the
user or the general public. It is not a full-fledged wiki.  The system
administrators can edit these pages via the web interface. This
feature can be disabled by the system administrators in the display
configuration page.


# Documents

There is a simple feature to store documents (files), such as PDFs or
XLSX files for any user to access. This can be used to provide the
users with templates or information documents. This feature can be
disabled by the system administrators in the display configuration
page.


# Interfaces

There are three main interfaces to the system, the web, the API
(Application Programming Interface) and the CLI (Command-Line
Interface).

The web interface behaves slightly differently depending on the role
of the user account logged in.


## Web

The web interace is the standard interface for accessing and using OrderPortal.

Depending on the role of the user account, the privileges in the web
interface differ. In principle, the ordinary user can view and edit
only her own orders. Staff can view most things, while admin can
perform all view and edit operations that are available in the web
interface.

## API

The Application Programming Interface (API) allows other systems to
interact with the order portal. It is based on RESTful principles
using JSON and linked data to allow other systems to access and/or
modify various data entities in the portal.

The API is currently fairly limited.

The web pages having a link
![](/static/json.png) `JSON`
which leads to the JSON format representation of the entity in the page.

The account to be used for API interactions must have its API key
set. That key provides authentication for programmatic access to the
API. Set it by checking the box `Set new API key` in the **edit page**
of your account. The user identified by the API key has the same
privileges in the API as in the web interface.

The JSON for the entities may contain links to other entities or
actions. The design is inspired by (but not identical to) the proposed
standard Hypertext Application Language (HAL). See Mike Kelly's
original proposal at http://stateless.co/hal_specification.html and
the (defunct) IETF proposal at
https://tools.ietf.org/html/draft-kelly-json-hal-08. The most
important difference is that the key `links`, rather than `_links`, is
used.

There are a number of sample scripts showing various interactions with
the API. Note that the example script uses the third-party
module `requests` (see
[here](http://docs.python-requests.org/en/master/ "!")) which is much
nicer to work with than the standard Python `urllib` module.

### API Get order data

An example script that gets all data about an order in JSON format is
provided here:
[get_order.py](https://github.com/pekrau/OrderPortal/blob/master/api_scripts/get_order.py "!").

The data obtained is the same as one gets by clicking the JSON link in
the upper right corner of the order's web page.

One should note that the order can always be identified by its
IUID. If the site has enabled identifiers (which typically look
something like XYZ00102), then it is possible to use that identifier
instead of the IUID for this particular case. For some cases, the IUID
must be used in the URL. The IUID is the safest bet, so if you have it
readily at hand, use it.


### API Create order

An order can be created by POST of JSON data containing the IUID of
the relevant form, and optionally a title. The returned data will
contain the full representation of the newly created order, which will
contain no data for the fields.

It is not possible to set any initial values of the fields using this
call. You will have to set the field values using a separate edit (see
[Edit an order](/documentation#edit-order]).

For an example order create script, see
[create_order.py](https://github.com/pekrau/OrderPortal/blob/master/api_scripts/create_order.py "!").


### API Edit order

An order can be edited by POST of JSON data containing the fields to
change. In principle, the data to send should look like a subset of
the full JSON representation of an order.

Fields that are not included in the data are not touched. Only fields
present in the form for the order can be set, and only when the
current user is allowed to do so. Attempts to set other fields will be
silently ignored.

In addition to the fields, the title, tags and history of an order can
also be set via the API.

**NOTE**: setting history explicitly should be done with care, so as
to avoid fake data in the history. The point of the history is to
show when status changes happened without having to go through the
entire log of the order.

For an example order edit script, see
[edit_order.py](https://github.com/pekrau/OrderPortal/blob/master/api_scripts/edit_order.py "!").


### API Set order status

The API can be used to set the status of an order. The allowed status
transitions are the same as in the web interface, and depend on the
current status of the order and the role of the account.

The allowed transitions and their URLs are provided in the JSON data
for the order in the form of a dictionary with the target states as
key and as value another dictionary with the key ``href`` and the
corresponding URL as value. One must use the HTTP method POST for
these URLs, since they change the order.

See the example script
[submit_order.py](https://github.com/pekrau/OrderPortal/blob/master/api_scripts/submit_order.py "!")
for the code used to submit an order. Similar code is used for other
status transitions.


### API Add order report

A report for an order can be added by doing a PUT to the order
report URI with the report content file as request body.

The content type (MIME type) of the data is recorded with the
report. If it is `text/html` or `text/plain`, the content will be
display in-line in the user's browser. Otherwise the content will be
downloaded as a file to the user's browser when the report button is
clicked.

For an example add report script, see
[add_report.py](https://github.com/pekrau/OrderPortal/blob/master/api_scripts/add_report.py "!").


## CLI

The Command Line Interface (CLI) allows system various maintenance
operations, such as backup, account creation and such. It is executed
on the command line of the machine which hosts the OrderPortal
instance. This means that only users with accounts of sufficient
privilege on this machine can use it.


# Backup

Backups of the CouchDB database can easily be produced using the CLI:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py dump

This creates a `tar.gz` file with today's date in the file name. There are command
options for setting the name of the file, or the directory in which it is written.
See the `--help` option of the CLI.


# Instructions

## Creating order form

A system administrator will have to prepare a form for the end-user to
be able to prepare an order.

Like so:

- Go to the [forms list page](/forms "!").
- Click the button "Create form".
- Fill in the title and description. These can be edited later.
- Click "Save".

Now add fields. A "group" field is a container for other fields, and does
not contain a value of its own. The other types of fields are fairly
self-explanatory.

- Click "Create field".
- Choose group. If no groups have been created, only the top level is
  available. This choice cannot be edited later.
- The identifier must be like a common programming language identifier:
  Begin with an alphabetical character, and then any number of alphanumerical
  and underscore characters. No blanks. It must be unique within the form.
  It cannot be edited later.
- The label is what is shown for the user. If none, then the identifer will
  be shown, somewhat prettified. Can be edited later.
- The field can be made read-only for user, or invisible to the user. Can be
  edited later.
- The description is the help text visible to the user. Can be edited later.
- Click "Save."
- The field will be added below the others in its group. The placement in
  the group can be edited later.
- If you make a mistake (giving wrong identifier, placing in wrong group,
  etc) you will probably have to delete the field and try again. Currently,
  only the label, access, placement and description can be edited later.
- Conditional visibility is specified when editing a field. Currently,
  only a single value in another select field can be tested against.

After having added some fields, it is possible to test what an order for it
will look like: Click "Testing". This will allow only the system administrators
to create and edit a test order for the form.

Once done with testing, click "Pending" to allow editing of the form again.
Any orders created while "Testing" will automatically be deleted.

**Do not click "Enable"!** That will enable the form for users to create
orders. This **cannot be undone!** So be sure that the form is OK before
you do this.

# Installation

The current installation procedure is described in README for the
[GitHub repo](https://github.com/pekrau/OrderPortal "!").
