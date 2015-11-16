OrderPortal
===========

Background
----------

The OrderPortal system was created to satisfy the needs of the
[National Genomics Infrastructure Sweden](http://www.scilifelab.se/platforms/ngi/),
which is a service facility producing sequence data from DNA and
RNA samples provided by external researchers. The facility processes
the samples according to the order from the scientist.


Features
--------

A portal where users (researchers) can place orders for a project to
be executed by a research service facility was required. The portal
should have the following features:

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

The system is a portal for orders (_a.k.a._ requests, project
applications) to one single facility from its users. A user is a
researcher external to the service facility, and is usually the
Principal Investigator (PI) for one or more projects.

The OrderPortal system is designed for only one facility, having a
single order input form, which can be hierarchically organized. The
system can be used for several facilities within the same organisation
by running several completely separate instances of it.

A user account is defined within each OrderPortal instance separately.
We decided against a design based on a single central user account
database for all facilities.  The email address of the user is used as
the user account identifier.

The design of the order form setup is fairly general; there is nothing
that is hardcoded for specific domains of science. The content of the
order form is defined by the facility admins.

The design of the system is kept as flexible and general as
possible. The base template and CSS are to some extend modifiable (via
command line operations), allowing the appearance of the OrderPortal
to be customised.

The order form
--------------

The order form fields are fully configurable by the facility admins
via the web interface. The field definitions are generic, and allow
order forms to be designed for a wide variety of facilities.

The order form must allow hierarchical grouping of fields, with
dynamic display according to rules. This allows for cases where a
top-level selection of e.g. a specific technology determines which
further input fields are required to be filled in.

When the order form for a facility is changed, previously submitted
orders are not affected. It will not be possible (at least in the
initial version) to change the form for previously created orders.

Only orders, no info pages
--------------------------

The system is minimalistic in the sense that it handles only
orders. There is no general wiki or blog function for describing the
context of the orders. Such needs must be handled by other systems.

Facility
--------

The term facility is used for the organisation providing the service
specified by the order form. One instance (database) of the system
handles one facility. All entities in the database belong to one and
only one facility.

There are three reasons for this design choice:

1. Security between facilities. The existence and contents of a
   particular project in one facility must not be visible to the
   admins or staff of another facility. This is a strict requirement
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

There are basically three kinds of users:

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

It must be possible to reassign an order from one user to another, to
facilitate personnel changes.

An external scientist applies for a user account by providing the
relevant information. Such an account is created with a status of
"pending".  The admin reviews the pending user account and enables it
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

The admin designs the set of fields which are to be filled in by the
user for an order. This involves the following parameters for a field:

- Field identifier
- Field data type
- Is a field value required?
- Field description
- Value options, if relevant
- Hierarchy and order, including conditional visibility
- Visibility to the user; some fields may be visible only to the staff

When an order is created, its fields definitions are copied from the
current set. Thus, an order is always self-contained.  Once an order
has been created, its fields and selected options are effectively
frozen, and remain fixed even if the current fields are updated.

The set of fields defined for the site may change, but the structure
of the order stays the same. This allows any change of the current set
of fields, while maintaining the integrity of old orders. The
disadvantage is that it makes it hard to update old orders with any
new fields.

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is necessary for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

The data in all dependent fields deselected by a choice in a
high-level conditional field should be set as undetermined when the
order is saved by the user. This simplifies interpretation of the
order data by other external systems.


Order
-----

An order is a copy of all fields at the time of its creation. It
belongs to a user. It is editable by the user until it has been
submitted for approval by the facility staff.

An order may contain fields which require a value. An order lacking a
required value can be saved, but it cannot be submitted. This allows
the user to create and fill in orders only partially, and to return to
the order at a later date to complete it.

An order can have one and only one state. The following is the list
of standard states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Created, and possibly edited.                        |
| SUBMITTED   | Submitted by user.                                   |
| REVIEW      | Under review by the facility.                        |
| ACCEPTED    | Checked and accepted by the facility.                |
| REJECTED    | Rejected by facility.                                |
| PENDING     | Awaiting further input from user.                    |
| QUEUED      | Facility has placed the order in its work queue.     |
| WORKING     | Work is on-going, in the lab or in data analysis.    |
| WAITING     | Work has paused, for whatever reason.                |
| CANCELLED   | Project stopped by the user.                         |
| ABORTED     | Project stopped by the facility.                     |
| FINISHED    | Work has been finalized.                             |
| DELIVERED   | The results have been delivered to the user.         |
| INVOICED    | The user has been invoiced.                          |
| CLOSED      | All work and steps for the order have been done.     |
| ARCHIVED    | The order has been archived; cannot be changed.      |

The states and allowed transitions are defined in a YAML configuration
file for a facility. This allows a facility to define other states and
transitions than the standard ones. It also allows new states and
transitions to be added to an existing setup. Removing existing states
may break the system, and should not be attempted; instead, the transitions
should be modified to avoid the redundant state.

Publications
------------

The system should include a feature to allow facility coordinators
and/or users to curate a list of publication references associated
with the user, and possibly the order.

This will be of help when preparing reports for the grant review of a
facility.

Interface
---------

There are two main interfaces to the system, the web and the API. The
web interface behaves differently depending on the type of the user
account logged in.

### User web interface

This is for human users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

### Staff web interface

This is for normal facility staff usage. Display of orders according
to state and other parameters.

### Admin web interface

For admins only, this interface enables editing orders, users and
fields. This includes the ability to move orders along into different
states.

### The Application Programming Interface (API)

The API allows other systems to interact with the order portal. It is
based on RESTful principles using JSON and linked data to allow other
systems to access and/or modify various data entities in the portal.

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
to an order or to a sample. Both users and facility staff should be
allowed to do this.

Links
-----

Links to other web pages can be set for orders and samples, allowing
users to navigate to other relevant information systems. Both facility
staff and users should be able to set this.

Status
------

The system should allow display of a status page, in which the current
state of the project corresponding to the order is provided to the
user. The content of this page is extracted from other systems such as
the LIMS of the laboratory.

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored. The log trace is written by the system automatically
and cannot be edited by any user.
