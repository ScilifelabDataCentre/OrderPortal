OrderPortal
===========

A portal for orders (= requests, project applications) for one or more
facilities.

The goal of this system is to satisfy the needs of a lab facility
which produces DNA sequence data from biological samples. The samples
are provided by external researchers. The facility processes the
samples according to the order from the scientist, and this system is
capable of displaying the current status of the order and the
resulting data and metadata.

In addition, the needs of other similar scientific facilities
operating within the same organisation require a solution. This system
allows independent facilities to handle their own orders, using a
common database for user accounts.

The design of the order form setup is such that this software system
should be applicable to other areas; there is nothing that is
hardcoded for scientific or genomics data per se. The form content
must be easy to change, and previously submitted orders must not be
affected by such changes, unless explicitly requested.

We are striving to keep the design as general as possible, given the
requirements of the fundamental task.

Only orders, no info pages
--------------------------

The system is minimalistic in the sense that it handles only
orders. There is no general wiki or blog function, which is usually
required for a scientific facility to describe the available
services. Such needs should be handled by other systems.

Facility
--------

The organisation providing the service specified by the order
form. The system can handle more than one facility. All entities,
except the user, belong to one and only one facility.

User
----

A user is an account in the system. All editing operations, and most
viewing operations, require that the user is logged in.

There are basically two kinds of users:

1. An external scientist, who uses the portal to place one or more
   orders, and to follow the progress of an order.

2. Facility staff, including facility administrator, who may view and edit 
   all orders for their facility. The access privileges are determined by
   the system administrator.

Access privileges
-----------------

The facility staff is allowed to view and edit only data belonging to
their facility.

An external scientist should be able to view a page where all his/hers
orders are shown, regardless of facility.

A user should be allowed to specify which other users should be
allowed access to their orders.

Order template
--------------

An order template is the class of a set of orders. When an order is
create by the user, the current template is copied. It is used to
produce the form displayed for the user to fill in the relevant
values.

This design allows the facility staff to modify the order template
without invalidating any existing orders. These remain unchanged. A
special mechanism must then be put in place if existing orders (not
yet submitted?) are also to be updated by some change.

An order template belongs to a facility, and can be modified only by
the facility staff.

An order template should be possible to clone, to facilitate creating
new templates.

An order template can have one of the following states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Newly created, and/or being edited.                  |
| PUBLISHED   | Available to make orders from.                       |
| ARCHIVED    | No longer available to make orders from.             |

All state transitions are allowed by default. An order is not affected
by the state changes of its original template.

**Implementation note**: The states and allowed transitions should be
defined in a configuration file (e.g. YAML) for each facility. This
allows a facility to define other states than the default ones. It
also allows new states to be added to an existing setup. The question
whether current states should be possible to remove is left for a
future decision; the assumption is that this is not allowed.

Order
-----

An order is an instance of an order template. It belongs to a user and
a facility. It is editable by the user until it has been submitted for
approval by the facility staff.

An order may contain fields which require a value. The design is such
that the order can be edited and saved many times without setting such
required values, but it is not possible to submit it until all
required values have been entered.

The form displayed for an order is defined by the data copied from the
order template when it was required. The display allows hierarchical,
conditionally displayed subfields. The input fields should be
specifiable for different types of values; integers, positive
integers, floats in ranges, text, selections, etc.

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
defined in a configuration file (e.g. YAML) for each facility. This
allows a facility to define other states than the default ones. It
also allows new states to be added to an existing setup. The question
whether current states should be possible to remove is left for a
future decision; the assumption is that this is not allowed.

Interface
---------

There are two interfaces to the system:

### The web interface

This is for human users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

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

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored. Neither facility staff nor users are allowed to edit
the log trace explicitly.
