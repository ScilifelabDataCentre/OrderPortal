OrderPortal
===========

A portal for orders (_aka._ requests, project applications) for a facility.

The system has been created to satisfy the needs of a lab facility
which produces DNA sequence data from biological samples. The samples
are provided by external researchers. The facility processes the
samples according to the order from the scientist, and this system
keeps the user up to date with the current status of the order and any
resulting data and metadata.

OrderPortal has been written to extend to the needs of other similar
scientific facilities operating within the same organisation. It
can be instantiated for any number of facilities, using a common
database of user accounts.

The design of the order form setup must allow its application to other
domains; there is nothing that is hardcoded for scientific or genomics
data _per se_. The form content must be easy to change, and previously
submitted orders must not be affected by such changes, unless
explicitly requested.

We are striving to keep the design as flexible and general as possible.
The base template and CSS will be editable, allowing the appearance of
the OrderPortal to be customised.

Only orders, no info pages
--------------------------

The system is minimalistic in the sense that it handles only
orders. There is no general wiki or blog function for describing the
context of the orders. Such needs should be handled by other systems.

Facility
--------

The term facility is used for the organisation providing the service
specified by the order form. One instance (database) of the system
handles one facility. All entities in the database, except the user
account, belong to one and only one facility.

There are two reasons for this design choice:

1. Security between facilities. The fact that a particular project is
   present in one facility must not be visible to the administrators of
   another facility. This is a strict requirement from some facilities,
   and it is easier to implement if the databases for each facility is
   strictly separate from one another.

2. The styling of an order portal is much easier to implement if each
   facility has its own portal instance.

One drawback with this design choice is that it makes it more
difficult to allow the users to see all their orders in all
facilities.


Users
-----

A user is an account in the system. All editing operations, and most
viewing operations, require that the user is logged in.

There are basically three kinds of users:

1. An external scientist, who uses the portal to place one or more
   orders, and to follow the progress of an order. In principle, this
   type of user can place orders with any facility.

2. Facility staff, including facility administrator, who may view and edit 
   all orders for their facility.

3. System administrators, who are allowed to view and edit all aspects
   of the system. This user account should only be used to perform system
   maintenance. It should not be used for any actual processing of orders.

Authentication uses one single database, meaning that the same user account
can be used to access to different facilities.

User accounts can be set as inactive, for example if the person
leaves, or as a means of blocking invalid use. Deletion of a user
account is never allowed (except in special circumstances, only by
system administrators), to allow full traceability of old orders.

New registrations must be approved by facility staff.


Access privileges
-----------------

The facility staff is allowed to view and edit only data belonging to
their facility.

An external scientist should by default be able to place orders with
any facility, once the user's account has been approved.

A user should be allowed to specify which other users will be
allowed access to their orders within each facility. 


Order template
--------------

The order template describes the currently valid set of fields and
options that can be entered into an actual order prepared by a
user. The order template contains fields that are editable by the
facility staff, determining name, data type, order in the form,
default value, required or not, and other properties.

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is necessary for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

The data in all dependent fields deselected by a choice in a
high-level conditional field should be set as undetermined when the
order is saved by the user. This simplifies interpretation of the
order data by other external systems.

Each time an order is edited by the user, the order is displayed
according to the current order template.

Once an order has been submitted, its fields and selected options are
effectively frozen, and remain fixed even if the order template is
updated. The facility administrators are allowed to edit a submitted
order.

This design allows the facility staff to modify the order template
without invalidating any existing submitted orders. Fields and options
are never deleted, only removed from the current template when depreciated.

The order template can be modified only by the facility staff.

Order
-----

An order is an instance of the order template. It belongs to a
user. It is editable by the user until it has been submitted for
approval by the facility staff.

An order may contain fields which require a value. An order lacking a
required value can be saved, but it cannot be submitted. This allows
the user to create and fill in orders only partially, and to return to
the order at a later date to complete it.

An order can have one of the following states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Created, edited, but lacking some required value.    |
| READY       | All require values are present; submittable.         |
| SUBMITTED   | Submitted by user.                                   |
| REVIEW      | Under review by the facility.                        |
| ACCEPTED    | Checked by facility, and found OK.                   |
| REJECTED    | Rejected by facility.                                |
| PENDING     | Awaiting further input from user.                    |
| WORKING     | Work is on-going, in the lab or in data analysis.    |
| QUEUED      | Facility has placed the order in its work queue.     |
| WAITING     | Work has paused, due to either user or facility.     |
| ABORTED     | Stopped by the user.                                 |
| CANCELLED   | Stopped by the facility.                             |
| FINISHED    | Work has been finalized.                             |
| DELIVERED   | The results have been delivered to the user.         |
| INVOICED    | The user has been invoiced.                          |
| CLOSED      | All work and steps for the order have been done.     |
| ARCHIVED    | The order has been archived, no longer visible.      |

**Implementation note**: The states and allowed transitions should be
defined in a database or configuration file (e.g. YAML) for each
facility. This allows a facility to define other states than the
default ones. It also allows new states to be added to an existing
setup. The question whether current states should be possible to
remove is left for a future decision; the assumption is that this is
not allowed.

Interface
---------

There are three interfaces to the system:

### The facility web interface

This is for human users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

### User administration web interface

For system administrators only, this is a simple interface that allows
deletion and other non-standard modifications to existing users.

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
what" is stored. Neither facility staff nor users are allowed to edit
the log trace explicitly.
