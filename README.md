OrderPortal
===========

The OrderPortal system is a web-based portal that allows form-based
submission of information from users to a facility. It was designed
academic service facilities that handle discrete orders or project
proposals, reports, etc, from its researcher users. It has also been
used as a system to gather reports from researchers and research
units.

## Installation

The current version has been developed using Python 3.10 or higher.
It may work on Python 3.8 and 3.9, but this has not been tested.

### Docker containers

Docker containers for the releases can be retrieved from
[ghcr.io/pekrau](https://github.com/pekrau/OrderPortal/pkgs/container/orderportal).


### From source code

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

The OrderPortal server and the CLI (command-line interface) must be
executed in a Python environment where all the required dependencies
have been installed, as specified by the file `requirements.txt`.  It
is recommended that a virtual environment is created for this. Refer
to the documentation for the virtual environment system you are using.

Download and install the required third-party Python modules using the
`requirements.txt` file as approprate for your Python environment.

    $ sudo pip install -r requirements.txt

### Settings file

From version 11.0 of OrderPortal, it is possible to use only environment
variables for the basic configuration of the system. All other configurations
have been moved into the database, and can be modified using the web interface.

However, it is still possible to use a YAML settings file for the basic configuration.
On startup, the OrderPortal system looks for a `settings.yaml` file first by the
file path given by the environment variable ORDERPORTAL_SETTINGS_FILEPATH, and
in second place by the file path `OrderPortal/site/settings.yaml`. The first of
these files found, if any, will be used.

If both an environment variable and an entry in a `settings.yaml` file defines
a configuration value, then the environment variable takes precedence.

See the comments in the template file
`OrderPortal/settings_template.yaml` file for editing the file for
your site. In particular, the CouchDB variables must be set (see
below).

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

Set the correct values for the CouchDB variables in the `settings.yaml` file
(see above). Otherwise the following operations will fail.

Create the database in CouchDB using the command-line interface (CLI).

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py create-database

Create the first OrderPortal system administrator account in the database using the CLI:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python3 cli.py create-admin

### `Tornado` server

The `tornado` server should be executed as a system service. This depends
on your operating system; refer to its documentation.

It is recommended that you use a reverse proxy for the `tornado`
server, e.g. `nginx` or `apache`. See the documentation for those
systems.

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
define the database indexes) are automatically updated when the
`tornado` server is restarted.
