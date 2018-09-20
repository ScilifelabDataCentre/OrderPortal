OrderPortal
===========

A portal for orders (requests, project applications, etc) to a
facility from its users.

See also:

- [INSTALLATION.md](INSTALLATION.md).

The [GitHub wiki](https://github.com/pekrau/OrderPortal/wiki) contains
technical instructions and information.

Background
----------

The OrderPortal system was created to satisfy the needs of the
[National Genomics Infrastructure (NGI) Sweden](https://ngisweden.scilifelab.se/),
which is a service facility for DNA sequencing and genotyping on
samples provided by external researchers. The facility processes
the samples according to the order from the scientist.

The OrderPortal system has been designed to work for any type of
service facility that handles discrete orders. It may also be used for
other uses, such as project applications, report submission, etc. The
system allows basically any type of form-based submission of
information.

The OrderPortal system is not hardcoded for any specific area such as
DNA sequencing. On the contrary, considerable effort has gone into
making sure the design is as general as possible. This means that
installation of the system requires configuration of a number of
aspects to suite your particular needs.

Features
--------

We (NGI Sweden) needed a portal where users (researchers) can place
orders for a project to be executed by a research service
facility. The portal had to have the following features:

* Allow users to register an account, which is approved by the facility staff.
* Allow the user to specify an order.
* Allow the user to submit the order to the facility.
* Let the facility staff keep track of review and agreements.
* The facility staff can accept an order, thus transforming it
  into a project.
* Allow input from the user of required project data, such as sample sheets.
* Allow attaching various documents to an order.
* Display project status reports.
* Allow keeping track of Key Performance Indicators (KPIs), facilitating
  resource usage reports for the facility.

Design outline
--------------

The system is a portal for orders (requests, project applications,
etc) to a single facility from its users. A user is a researcher
external to the service facility, and may or may not be the Principal
Investigator (PI) for one or more projects.

An order is created from a template which is called a form in this
system. The facility administrators must set up and publish the order
forms for a researcher to be able to create and order. Each form
contains data fields that can be hierarchically organized.

The OrderPortal system is designed for only one facility, displaying
maybe 3-8 different order forms. The system can be used for several
facilities within the same organisation by running several independent
OrderPortal instances. Each instance must use its own database.

A user account is defined within each OrderPortal instance separately.
We decided against a design based on a single central user account
database for all facilities. The email address of the user is used as
the user account identifier.

The design of an order form is fairly general; there is nothing that
is hardcoded for specific domains of science. The content of the order
forms consists of a different fields for different types of input
data. The order forms are defined by the facility administrators. An
order form can be used only when it has been enabled. An outdated
order form can be disabled; its orders will still be accessible.

The design of the system is kept as flexible and general as
possible. Customisation of site logo and title is possible, and the
information pages are under control of the facility administrators.

The order form
--------------

The order form fields are fully configurable by the facility administrators
via the web interface. The field definitions are generic, and allow
order forms to be designed for a wide variety of input data.

The order form allows hierarchical grouping of fields, with
dynamic display according to rules. This allows for cases where a
top-level selection of e.g. a specific technology determines which
further input fields are required to be filled in.

When the order form for a facility is changed, previously submitted
orders are not affected. It is not possible to change the form for
previously created orders.

Simple info page facility
-------------------------

There is a very simple information page facility in the system. This
is not by far a full-fledged wiki, so it can be used only for basic needs.
All administrators in the system can edit these pages via the web interface.

Facility
--------

The term facility is used for the organisation providing the service
specified by the order form. One instance (database) of the system
handles one facility. All entities in the database belong to one and
only one facility.

There are three reasons for this design choice:

1. Security between facilities. The existence and contents of a
   particular project in one facility must not be visible to the
   administrators or staff of another facility. This is a strict requirement
   for some facilities, and it is easier to implement if the databases
   for each facility is separate from one another.

2. The styling of an order portal is much easier to implement if each
   facility has its own portal instance.

3. The introduction, or elimination, of a facility in the overall
   organisation becomes much easier if every instance of the system is
   independent of the other.

One drawback with this design choice is that it complicates the
communication between and linking of different but related projects in
different facilities.


Users
-----

A user is an account in the system. Almost all operation require that
the user is logged in. The email address is the user account identifier.

There are three kinds of users:

1. User: An external scientist, who uses the portal to place one or
   more orders, and to follow the progress of their own orders. The
   "customer" of the facility.

2. Staff: Facility staff, who may view all orders, but not change anything.

3. Admin: Facility administrators, a.k.a. project coordinators, who
   are allowed to view and edit all aspects of the system that can be
   modified via the web interface. This includes processing orders,
   modifying the order fields, and handling user accounts.

User accounts can be set as disabled, for example if the person leaves
her position, or as a means of blocking invalid use. Deletion of a
user account is not allowed, to allow full traceability of old
orders. An account can always be enabled again.

An external scientist applies for a user account by providing the
relevant information. Such an account is created with a status of
"pending". The administrator reviews the pending user account and enables it
if it appears legitimate. The user gets an email about the account
having been enabled and with instructions on how to set the password
for it.


Access privileges
-----------------

The user can place orders as soon has she has logged in.

A user is allowed to specify which other users will be able to access
to her orders. Access can also be granted to specific users for each
individual order.


Order: form and fields
----------------------

The administrator designs the forms and their set of fields which determine
what the user must fill in for an order. The administrator can clone a form in
order to make a new variant. Old forms can be disabled, and new forms
enabled, as needed.

Adding a field in a new form requires deciding on the followin parameters:

- Field identifier
- Field data type
- Is a field value required?
- Field description
- Value options, if relevant
- Hierarchy and order, including conditional visibility
- Visibility to the user; some fields may be visible only to the staff

When an order is created, its fields definitions are copied from the
form. Thus, an order is always self-contained. Once an order has been
created, its fields and selected options are effectively frozen, and
remain fixed. Only the values of the fields may be changed, not the
definition of them.

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is necessary for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

Order
-----

An order contains a copy of all fields from its form. It belongs to a
user. It is editable by the user until it has been submitted for
approval by the facility staff.

An order may contain fields which require a value. An order lacking a
required value can be saved, but it cannot be submitted. This allows
the user to create and fill in orders only partially, and to return to
the order at a later date to complete it.

An order can have one and only one status. The statuses available for
an order is configurable. Here is a list of standard statuses:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Created, and possibly edited.                        |
| SUBMITTED   | Submitted by user.                                   |
| REVIEW      | Under review by the facility.                        |
| ACCEPTED    | Checked and accepted by the facility.                |
| REJECTED    | Rejected by facility.                                |
| PROCESSING  | The facility is working on the project.              |
| ABORTED     | The project has been stopped.                        |
| CLOSED      | All work and steps for the order have been done.     |

The statuses and the allowed transitions between them are defined in a
YAML configuration file for a facility. This allows a facility to
define other statuses and transitions than the standard ones. It also
allows new statuses and transitions to be added to an existing
setup. Removing existing statuses may break the system, and should not
be attempted; instead, the transitions should be modified to avoid the
redundant status.

Interface
---------

There are two main interfaces to the system, the web and the API. The
web interface behaves differently depending on the type of the user
account logged in.

### User web interface

This is for ordinary users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

### Staff web interface

This is for normal facility staff usage. Display of orders according
to status and other parameters.

### Administrator web interface

For administrators only, this interface enables editing orders, users and
fields. This includes the ability to move orders along into different
statuses.

### The Application Programming Interface (API)

The API allows other systems to interact with the order portal. It is
based on RESTful principles using JSON and linked data to allow other
systems to access and/or modify various data entities in the portal.

Publications
------------

_Future feature_

Facility coordinators and/or users should be allowed to to curate a
list of publication references associated with the user, and possibly
with the order.

This will be of help when preparing reports for the grant review of a
facility.

Additional information
----------------------

Once an order has been submitted, additional information may be
required from the user. For example, a sample information sheet may be
requested by the facility. The facility should be able to specify a
form for this, which should handle Excel and CSV files up- and
download.

Attached files
--------------

Files such as agreements, specifications, images, etc, can be attached
to an order or to a sample.

Links
-----

_Future feature_

Links to other web pages can be set for orders and samples, allowing
users to navigate to other relevant information systems. Both facility
staff and users should be able to set this.

Status
------

_Future feature_

The system should allow display of a status page, in which the current
status of the project corresponding to the order is provided to the
user. The content of this page is extracted from other systems such as
the LIMS of the laboratory.

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored. The log trace is written by the system automatically
and cannot be edited by any user.
