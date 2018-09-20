Installation
============

These installation instructions are valid for the instances running on
the data-office machine at SciLifeLab. It will have to be adapted for
other sites. In particular, the name "**xyz**" needs to be changed for your
case.

Please adjust or replace by whatever is mandated by the policies at your site.

Source code setup
-----------------

The Linux account `nginx` is used to host the SciLifeLab instance files.

Clone the GitHub repo:

    $ cd /var/www/apps
    $ sudo -u nginx mkdir xyz
    $ cd xyz
    $ sudo -u nginx git clone https://github.com/pekrau/OrderPortal.git

Create the `site` subdirectory using the template:

    $ cd OrderPortal/orderportal
    $ sudo -u nginx cp -r site xyz

The files in your `xyz` directory may need modification for your needs.
In particular, the YAML files may need to be adjusted or replaced.

All Python commands below rely on the Python path being correctly set.
This can be included in a `.bashrc` file or executed interactively:

    $ export PYTHONPATH="${PYTHONPATH}:/var/www/apps/xyz/OrderPortal"

Download and install the required third-party Python modules using the
`requirements.txt` file. Whether you should do this as `root` or some other
user depends on your policy.

    $ sudo pip install -r requirements.txt

The command code examples below assume that the PYTHONPATH environment
variable has been set, as shown above.

Settings file
-------------

Create the settings file and edit its contents according to your site. Some
of the settings depend on actions described below.

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx cp settings_template.yaml settings.yaml
    $ sudo -u nginx chmod go-r settings.yaml
    $ sudo -u nginx emacs settings.yaml

See the comments in the settings file.

CouchDB setup
-------------

It is assumed that you already have a CouchDB instance running.

- Go to the CouchDB web interface.
- Create the CouchDB user **orderportal_xyz**. This may be done by
  signing up as that user.
- Log in as CouchDB admin. Set the password for the user **orderportal_xyz**:
  - Go to the database **_users** and open the document for the user
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

Initialize the database in CouchDB to load the design documents (index
definitions). This requires a valid **settings** file.

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx python2 init_database.py

Create the first admin account in the database by running a script that
will interactively ask for input:

    $ sudo -u nginx python2 create_admin.py

Logging
-------

The settings file may define the file path of the log file (variable
LOGGING_FILEPATH), if any. The log file must be located in a directory which
the tornado server can write to. For example:

    $ cd /var/log
    $ sudo mkdir orderportal_xyz
    $ sudo chown nginx.nginx orderportal_xyz

System service
--------------

The tornado server should be executed as a system service. This depends
on the operating system. For SELinux, a template systemd file is available at
[site/orderportal_xyz.service](https://github.com/pekrau/OrderPortal/blob/master/orderportal/site/orderportal_xyz.service).

nginx configuration
-------------------

In our case, the tornado server is made available by reverse-proxy
through nginx. The template nginx file is available at
[site/orderportal_xyz.conf](https://github.com/pekrau/OrderPortal/blob/master/orderportal/site/orderportal_xyz.conf).

Backup
------

Backup relies on running a script to dump all data in the CouchDB database
to a tar file. Create a backup directory:

    $ sudo mkdir /home/backup/backup_files/orderportal_xyz

Copy the template bash backup script
[site/orderportal_xyz.bash](https://github.com/pekrau/OrderPortal/blob/master/orderportal/site/orderportal_xyz.bash):

    $ cd /etc/scripts
    $ sudo cp dump_orderportal_facrep.bash dump_orderportal_protcore.bash

The crontab entry should look like this:

45 22 * * * /etc/scripts/dump_orderportal_protcore.bash


Maintenance, updates
--------------------

To update the source code from the GitHub repo:

    $ cd /var/www/apps/xyz/OrderPortal
    $ sudo -u nginx git pull
    $ sudo systemctl {status|start|stop|restart} orderportal_xyz

If not done, set the PYTHONPATH environment variable:

    $ cd /var/www/apps/xyz/OrderPortal
    $ export PYTHONPATH="${PYTHONPATH}:${PWD}"

To load any new CouchDB design documents (i.e. index definitions):

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx python2 load_designs.py

Unless the OrderPortal app is running in debug mode, the tornado server
will have to be restarted.

    $ sudo systemctl restart orderportal_xyz.service
