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

A user us an account for an external scientist to place one or more
orders, and to follow the progress of an order.

It is also an account for the facility staff, who may view and edit
all orders for their facility. The access privileges are determined by
the system administrator.

Access privileges
-----------------

The facility staff must only be able to see data belonging to their
facility.

An external scientist should be able to view a page where all orders
are shown, regardless of facility.

A user should be allowed to specify which other users are to be
allowed access to their orders by default. Access should then also be
editable on an order-by-order basis.

A user should be able to set the level of email communication for an
order, or generally.

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

An order template can have one of the following states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Newly created, and/or being edited.                  |
| PUBLISHED   | Available to make orders from.                       |
| ARCHIVED    | No longer available to make orders from.             |

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
conditionally displayed subfields.

An order can have one of the following states:

| State       | Semantics                                            |
|-------------|------------------------------------------------------|
| PREPARATION | Created, edited, but lacking some required value.    |
| READY       | All require values are present; submittable.         |
| SUBMITTED   | Submitted by user.                                   |
| REVIEW      | Under review by the facility.                        |
| ACCEPTED    | Checked by facility, and found OK                    |
| REJECTED    | Rejected by facility.                                |
| ABORTED     | Stopped by the user.                                 |
| CANCELLED   | Stopped by the facility.                             |
| PENDING     | Awaiting further input from user.                    |
| QUEUED      | Facility has placed the order in its work queue.     |
| PROCESSING  | Work is on-going.                                    |
| WAITING     | Work has paused, due to either user or facility.     |
| FINISHED    | Work has been finalized.                             |
| DELIVERED   | The results have been delivered to the user.         |
| INVOICED    | The user has been invoiced.                          |
| CLOSED      | All work and steps for the order have been done.     |
| ARCHIVED    | The order has been archived, no longer visible.      |

Sample form
-----------

A form to be filled in by the user to provide information about the
samples for an order. A template is defined by the facility staff.  It
should be possible to download and upload Excel or CSV files.

Attached files
--------------

Files such as agreements, specifications, images, etc, can be attached
to an order or to a sample.

Links
-----

Links to other web pages can be set for orders and samples. Both
facility staff and users should be able to set this, allowing users to
navigate to other relevant information systems.

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored.

API
---

The interface provides an API for interaction with other systems.
