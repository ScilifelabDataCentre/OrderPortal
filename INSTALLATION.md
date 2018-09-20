Installation
============

These installation instructions are valid for the instances running on
the data-office machine at SciLifeLab. It will have to be adapted for
other sites. In particular, the name "xyz" needs to be changed for your
case.

Source code setup
-----------------

The SciLifeLab instances are setup as the nginx user.

Clone the GitHub repo:

    $ cd /var/www/apps
    $ sudo -u nginx mkdir xyz
    $ cd xyz
    $ sudo -u nginx git clone https://github.com/pekrau/OrderPortal.git

Create the site subdirectory using the template:

    $ cd OrderPortal/orderportal
    $ sudo -u nginx cp -r site xyz

Create the settings file and edit its contents according to your site.

    $ sudo -u nginx cp settings_template.yaml settings.yaml
    $ sudo -u nginx chmod go-r settings.yaml
    $ sudo -u nginx emacs settings.yaml

CouchDB setup
-------------

It is assumed that you already have a CouchDB instance running.

- Go to the CouchDB web interface.
- Create the CouchDB user **orderportal_xyz**. This may be done by
  signing up as that user.
- Log in as CouchDB admin. Set the password for the user **orderportal_xyz**:
  - Go to the database **_user** and find the document for the user
    **orderportal_xyz**.
  - Create a new field with the key "password", and set its value to the
    secret password. This password must be edited into the settings file.
  - When you save the document, CouchDB will hash the password and remove
    the password field.
- Create the database **orderportal_xyz** in CouchDB.
- Click on "Security..." and ensure that only the proper user can access it:
  - In the Names field of Admins, add the user name like so:
    `["orderportal_xyz"]` (a string in a list).
  - In the Names field of Members, add a dummy user name like so:
    `["dummy"]` (a string in a list).
  - The Roles fields should not be changed.

Maintenance
----------

To update the source code from the GitHub repo:

    $ cd /var/www/apps/xyz/OrderPortal
    $ sudo -u nginx git pull
    $ sudo systemctl {status|start|stop|restart} orderportal_xyz


