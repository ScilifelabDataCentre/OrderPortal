OrderPortal
===========

A portal for orders (requests, project proposals, etc) to a
facility from its users.

The [GitHub wiki](https://github.com/pekrau/OrderPortal/wiki) contains
some additional information.

Background
----------

The OrderPortal system allows basically any type of form-based
submission of information. It was designed to work for any type of
service facility that handles discrete orders or project proposals,
reports, etc.

The OrderPortal system was originally created to satisfy the needs of the
[National Genomics Infrastructure (NGI) Sweden](https://ngisweden.scilifelab.se/),
which is a service facility for DNA sequencing and genotyping on
samples provided by external researchers. The facility processes
the samples according to the order from the researcher.

The OrderPortal system is not hardcoded for any specific area such as
DNA sequencing. On the contrary, considerable effort has gone into
making sure the design is as general as possible. This means that
installation of the system requires specific settings suite your
particular needs.

Features
--------

* Allow users to register an account, which is approved by the facility staff.
* Allow the user to specify an order according to a predefined form.
* Allow the user to submit the order to the facility.
* Let the facility staff keep track of review and agreements.
* The facility staff can review, accept or decline an order.
* Allow input from the user of required project data, such as sample sheets.
* Allow attaching various documents to an order.
* Display project status reports.
* Allow keeping track of Key Performance Indicators (KPIs), facilitating
  resource usage reports for the facility.

Design outline
--------------

The system is a portal for **orders** (requests, project proposals,
etc) to a single facility from its users. A **user** is a researcher
external to the service facility, and may or may not be the Principal
Investigator (PI) for one or more projects.

An order is created from a template which is called a **form** in this
system. The facility administrators must set up and publish the order
forms for a researcher to be able to create an order. Each form
contains fields for data input by the researcher.

The OrderPortal system is designed for only one facility, displaying
up to about 8 different order forms. There is no hard limit to the
number of simultaneously published forms, but the current design does
not work well with more than 8 forms. If an organization has different
facilities requiring different sets of forms, then it is best to set
up different instances of the OrderPortal system, with different
back-end database instances.

A user account is defined within each OrderPortal instance.
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

The order form fields are fully configurable by the facility
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

Simple info pages
-----------------

There is a very simple information page subsystem. This is not by far
a full-fledged wiki, so it can be used only for basic needs.  All
administrators in the system can edit these pages via the web
interface. This feature can be disabled by modifying the settings.

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

Some configuration operations (settings variables) can only be done on
the command line on the machine hosting the system.


Access privileges
-----------------

The user can place orders as soon has she has logged in.

A user is allowed to specify which other users will be able to access
to her orders. Access can also be granted to specific users for each
individual order.


Order: form and fields
----------------------

The administrator designs the forms and their set of fields which
determine what the user must fill in for an order. The administrator
can clone a form in order to make a new variant. Old forms can be
disabled, and new forms enabled, as needed.

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
YAML configuration file. This allows a facility to define other
statuses and transitions than the standard ones. It also allows new
statuses and transitions to be added to an existing setup. Removing
existing statuses may break the system, and should not be attempted;
instead, the transitions should be modified to avoid the redundant
status.

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

This instruction is based on the procedure used for the instances
running on the SciLifeLab server. It will have to be adapted for your
site.

The Linux account `nginx` is used in the instructions below to host
the instance files. Change according to the policy at your site.

The name `xyz` is used below as a placeholder for the name of your instance.

Instructions for upgrading the OrderPortal software is given below
under [Updates](#updates).

Source code setup
-----------------

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

The OrderPortal server and the CLI must be executed in a Python
environment where all the required dependencies have been installed,
as specified by the file `requirements.txt`.  It is recommended that a
virtual environment is created for this. Refer to the Python
documentation.

Download and install the required third-party Python modules using the
`requirements.txt` file as approprate for your Python environment.

    $ sudo pip install -r requirements.txt

Settings file
-------------

Set the correction protection for the file `site/settings.yaml` and
edit it according to your setup. Some of the settings depend on
actions described below, so you may have to go back to edit it again.

    $ cd /var/www/apps/xyz/OrderPortal/site
    $ sudo -u nginx chmod go-rw settings.yaml
    $ sudo -u nginx emacs settings.yaml

See the comments in the template `settings.yaml` file for editing the
file for your site. In particular, the CouchDB variables must be set (see below).

CouchDB setup
-------------

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

Create the database in CouchDB using the command-line interface utility (CLI).

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py create-database

Create the first OrderPortal admin account in the database using the CLI:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py admin

`Tornado` server
--------------

The `tornado` server should be executed as a system service. This depends
on your operating system; refer to its documentation.

HTTP nginx configuration
------------------------

In our case, the `tornado` server is accessed through a reverse-proxy
via nginx. The template nginx file is available at
[orderportal/site_template/orderportal_xyz.conf](orderportal/site_template/orderportal_xyz.conf).
Copy, rename and edit it. In particular, ensure that the URL and port is
specified correctly.

    $ cd /etc/nginx/conf.d
    $ sudo cp /var/www/apps/xyz/OrderPortal/orderportal/site_template/orderportal_xyz.conf orderportal_xyzconf
    $ sudo emacs orderportal_xyz.conf

Backup
------

Backup relies on running the CLI to dump all data in the CouchDB database
to a tar file. Create a backup directory:

    $ sudo mkdir /home/backup/backup_files/orderportal_xyz

Copy and rename the template bash backup script
[orderportal/site_template/dump_orderportal_xyz.bash](orderportal/site_template/dump_orderportal_xyz.bash). It will also need editing, since it uses a SciLifeLab-specific tape-backup setup:

    $ cd /etc/scripts
    $ sudo cp /var/www/apps/xyz/OrderPortal/orderportal/site_template/dump_orderportal_xyz.bash dump_orderportal_xyz.bash

Edit the crontab file:

    $ export EDITOR=emacs
    $ crontab -e

The line in the crontab file should look something like this:

    45 22 * * * /etc/scripts/dump_orderportal_xyz.bash

Updates
-------

To update the source code from the GitHub repo:

    $ cd /var/www/apps/xyz/OrderPortal
    $ sudo -u nginx git pull
    $ sudo systemctl restart orderportal_xyz

Since version 3.6.19, the design documents are automatically updated
when the `tornado` server is restarted.

Please note that if your installation uses a repo forked from the
base, ensure that you have updated that repo first by making a pull
request and executing it.

Set up git commit signing.
