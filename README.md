OrderPortal
===========

A portal for orders (requests, project proposals, etc) to a
facility from its users.

The [GitHub wiki](https://github.com/pekrau/OrderPortal/wiki) contains
some additional information.

Background
----------

The OrderPortal system allows form-based submission of information. It
was designed to work for service facilities that handles discrete
orders or project proposals, reports, etc. It has also been used as a
system to gather reports from researchers and research units.

The OrderPortal system was originally created to satisfy the needs of the
[National Genomics Infrastructure (NGI) Sweden](https://ngisweden.scilifelab.se/),
which is a service facility for DNA sequencing and genotyping on
samples provided by external researchers. The facility processes
the samples according to the order from the researcher.

The OrderPortal system is not hardcoded for any specific area such as
DNA sequencing. On the contrary, considerable effort has gone into
making sure the design is as general as possible within the scope of
the basic problem it is intended to solve.

Since the system is general in character, the installation of it
requires specific configuration settings to suite your particular
needs.

Features
--------

* Allow users to register an account, which is enabled by the facility staff.
* Allows the system administrators to create predefined forms with a
  specific set of input fields.
* Allow the user to specify an order according to one of the predefined forms.
* Allow input from the user of required project data, such as sample sheets.
* Allow the user to submit the order to the facility.
* The facility staff can review, accept or decline an order.
* Let the facility staff keep track of review and agreements.
* Allow attaching various documents to an order.
* Display project status reports.
* Allow keeping track of Key Performance Indicators (KPIs), facilitating
  resource usage reports for the facility.

Basic concepts
--------------

The system is a portal for **orders** (requests, project proposals,
etc) to a single facility from its users. A **user** is a researcher
external to the service facility, and may or may not be the Principal
Investigator (PI) for one or more projects.

An order is created from a template which is called a **form** in this
system. The system administrators must set up and publish the forms
for a researcher to be able to create an order. Each form defines the
fields for data to be input by the researcher.

The OrderPortal system is designed for only one facility, displaying
up to about 8 different order forms. There is no hard limit to the
number of simultaneously published forms, but the current design does
not work well with more than about 8 forms. If an organization has
different facilities requiring different sets of forms, then it may be
better to set up different instances of the OrderPortal system, with
different back-end database instances.

The design of an order form is fairly general; there is nothing that
is hardcoded for specific domains of science. The content of the order
forms consists of a different fields for different types of input
data. The order forms are defined by the system administrators. An
order form can be used only when it has been enabled. An outdated
order form can be disabled; its orders will still be accessible for
processing. No new orders can be created from a disabled form.

A **user account** is defined within each OrderPortal instance. The email
address of the user is the user account identifier. This means that if
a user changes email address, a new account will have to be created.

Customisation of site logo and title is possible, and the information
pages are under control of the system administrators.

The order form
--------------

The order form fields are fully configurable by the system
administrators via the web interface. The field definitions are
generic, and allow order forms to be designed for a wide variety of
input data.

The order form allows hierarchical grouping of fields, with
dynamic display according to rules. This allows for cases where a
top-level selection of e.g. a specific technology determines which
further input fields are required to be filled in.

When the order form for a facility is changed, previously submitted
orders are not affected. It is not possible to change the form for
previously created orders.

Basic info pages
----------------

There is a very basic information page subsystem, intended to allow
displaying information about the orders and/or the facility to the
user or the general public. It is not a full-fledged wiki.  The system
administrators can edit these pages via the web interface. This
feature can be disabled by modifying the settings.

Facility
--------

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


Users
-----

A user is an account in the system. Almost all operation require that
the user is logged in. The email address is the user account identifier.

There are three kinds (=roles) of users:

1. User: An external scientist, who uses the portal to place one or
   more orders, and to follow the progress of their own orders. The
   "customer" of the facility.

2. Staff: Facility staff, who may view all orders, but are not allowed
   to change vary much.

3. Admin: System administrators who are allowed to view and edit all
   aspects of the OrderPortal system that can be modified via the web
   interface. This includes processing orders, modifying the order
   fields, and handling user accounts. Often, the project coordinators
   of the facility are designated as system administrators, since they
   will be using the system to keep track of incoming orders
   (projects).

User accounts can be set as disabled, for example if the person leaves
her position, or as a means of blocking invalid use. Deletion of a
user account is not allowed, to allow full traceability of old
orders. An account can be re-enabled.

An external scientist applies for a user account by providing the
relevant information. Such an account is created with a status of
"pending". The system administrator reviews the pending user account and
enables it if it appears legitimate. The user gets an email about the
account having been enabled and with instructions on how to set the
password for it.

Some configuration operations (settings variables) can only be done on
the command line on the machine hosting the system.


Access privileges
-----------------

The user can place orders as soon has she has logged in.

A user is allowed to specify which other users will be able to access
to her orders. Access can also be granted by a user to other specific
users for each individual order.


Order: form and fields
----------------------

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

- Field identifier
- Field data type
- Is a field value required?
- Field description
- Value options, if relevant
- Hierarchy and order, including conditional visibility
- Visibility to the user; some fields may be visible only to the staff

A field may be conditional, meaning that it is displayed only of some
other field has been assigned a specific value. This is necessary for
orders where the relevant fields depend on some high-level choice,
such a type of technology to use for a project.

Order
-----

An order contains a copy of all fields from its form. It belongs to
one and only one user. It is editable by the user until it has been
submitted.

An order usually contains fields which require a value. An order
lacking a required value can be saved, but it cannot be
submitted. This allows the user to create and fill in an order
partially and save it. Then, at a later data, she can return to the
order to complete it and then submit it.

An order can have one and only one status. The available statuses are
listed in the table. Only the statuses PREPARATION and SUBMITTED are
enabled by default.

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

Statuses can be enabled by the system administrators. Once enabled, a
status cannot be disabled. The reason for this is that already
existing orders may be in a specific status, or have a specific status
recorded in its history, and removing such a status would introduce
inconsistencies. The description of the semantic of a status can be
edited by the system administrators.

Transitions between the statuses can be edited by the system
administrators. The only transition enabled by default is the one from
PREPARATION to SUBMITTED.

Typically, enabling statuses and transitions should be done as part of
the configuration and testing phase before the instance is launched
into production. Here are some general guidelines:

- It is a good idea to keep the number of enabled statuses at a minimum.
  Since a status that has been enabled cannot be disabled, one should avoid
  cluttering the system with unnecessary statuses.
- Transitions should be set to those that are sensible given the typical workflow.
- Allowing too many transitions can lead to confusion and should be avoided.
- However, setting up transitions can be done freely, since they can be
  removed later without any problem.
- Since transitions can be enabled and disabled at will by the system
  administrators, it is always in principle possible (if cumbersome) to
  'rescue' an order which has been put in an incorrect status.

Interface
---------

There are three main interfaces to the system, the web, the API (Application Programming Interface) and the CLI (Command-Line Interface).

The web interface behaves slightly differently depending on the role
of the user account logged in.

### User web interface

This is for ordinary users. It should provide the user with sufficient
help and visual cues to allow filling in the form in a productive
manner. Missing values and values outside of allowed ranges must be
highlighted to help the user prepare a valid order.

### Staff web interface

This is for normal facility staff usage. Display of orders according
to status and other parameters.

### Administrator web interface

For system administrators only, this interface enables editing orders, users and
fields. This includes the ability to move orders along into different
statuses.

### The Application Programming Interface (API)

The API allows other systems to interact with the order portal. It is
based on RESTful principles using JSON and linked data to allow other
systems to access and/or modify various data entities in the portal.

The API is currently fairly limited.

### The Command Line Interface (CLI).

The CLI allows system various maintenance operations, such as backup, account
creation and such. It is executed on the command line of the machine which hosts
the OrderPortal instance. This means that only users with accounts of sufficient
privilege on this machine can use it. See below for more information.

Attached files
--------------

Files such as agreements, specifications, images, etc, can be attached
to an order or to a sample.

Links
-----

Links to other web pages can be set for orders and samples, allowing
users to navigate to other relevant information systems.
This feature can be disabled by modifying the settings.

Log
---

Each change of an order is logged, and the information "who, when,
what" is stored. The log trace is written by the system automatically
and cannot be edited by any user.

Installation
============

The current version has been developed using Python 3.10 or higher.
It may work on Python 3.8 and 3.9, but this has not been tested.

Docker containers
-----------------

Docker containers for the releases can be retrieved from [ghcr.io/pekrau](https://github.com/pekrau/OrderPortal/pkgs/container/orderportal).

From source code
----------------

This instruction is based on the old procedure used previously for the
instances running on the SciLifeLab server. It will have to be adapted
for your site.

The Linux account `nginx` is used in the instructions below to host
the instance files. Change according to the policy at your site.

The name `xyz` is used below as a placeholder for the name of your instance.

Instructions for updating the OrderPortal source code is given below
under [Updates](#updates).

### Source code setup

Download the `tar.gz` file for latest release from
[the Github repo](https://github.com/pekrau/OrderPortal/releases)
into the directory where the installation will be hosted. Substitute
the directory `/var/www/apps` with the corresponding on your machine:

    $ cd /var/www/apps
    $ sudo -u nginx mkdir xyz
    $ cd xyz
    $ ### Download OrderPortal-version.tar.gz to here.
    $ sudo -u nginx tar xvf OrderPortal-version.tar.gz
    $ sudo -u nginx mv OrderPortal-version OrderPortal

Create the `site` subdirectory for your instance by copying the
`site_template` directory.

    $ cd OrderPortal
    $ sudo -u nginx cp -r site_template site

The OrderPortal server and the CLI (command-line interface) must be
executed in a Python environment where all the required dependencies
have been installed, as specified by the file `requirements.txt`.  It
is recommended that a virtual environment is created for this. Refer
to the Python documentation.

Download and install the required third-party Python modules using the
`requirements.txt` file as approprate for your Python environment.

    $ sudo pip install -r requirements.txt

### Settings file

Set the correction protection for the file `site/settings.yaml` and
edit it according to your setup. Some of the settings depend on
actions described below, so you may have to go back to edit it again.

    $ cd /var/www/apps/xyz/OrderPortal/site
    $ sudo -u nginx chmod go-rw settings.yaml
    $ sudo -u nginx emacs settings.yaml

See the comments in the template `settings.yaml` file for editing the
file for your site. In particular, the CouchDB variables must be set (see below).

### CouchDB setup

Install and set up a CouchDB instance, if you don't have one
already. Follow the instructions for CouchDB, which are not included
here.

- Go to the CouchDB web interface, usually http://localhost:5984/_utils/
  if on the local machine and login.
- It is a good idea to create a new CouchDB CouchDB user account
  (e.g. `orderportal_xyz`) for your OrderPortal instance. It must have
  privileges to create and delete databases in CouchDB.
- However, it is possible to simply use the admin user account that you
  created when setting up the CouchDB instance.

Set the correct values for the CouchDB variables in the `site/settings.yaml` file
(see above). Otherwise the following operations will fail.

Create the database in CouchDB using the command-line interface (CLI).

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py create-database

Create the first OrderPortal system administrator account in the database using the CLI:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py admin

### `Tornado` server

The `tornado` server should be executed as a system service. This depends
on your operating system; refer to its documentation.

It is recommended that you use a reverse proxy for the `tornado`
server, e.g. `nginx` or `apache`. See the documentation for those
systems. A sample configuration file from an installation using `nginx` is
provided at [orderportal/site_template/orderportal_xyz.conf](orderportal/site_template/orderportal_xyz.conf).

### Backup

Backups of the CouchDB database can easily be produced using the CLI:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py dump

This creates a `tar.gz` file with today's date in the file name. There are command
options for setting the name of the file, or the directory in which it is written.
See the `--help` option of the CLI.

### Updates

To update the source code, simply download the latest release, unpack
the `tar.gz` file, and move the `OrderPortal` directory tree to the
correct location.  Ensure that you keep your `site` directory, and
that it is placed in the same location as before.

Since OrderPortal version 3.6.19, the CouchDB design documents (which
defined the indexes) are automatically updated when the `tornado`
server is restarted.
