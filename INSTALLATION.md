Installation
============

This installation instruction is derived from the procedure used for
the instances running on the data-office machine at SciLifeLab. It
will have to be adapted for your site.

The Linux account `nginx` is used to host the instance files. Change
according to the policy at your site.

The name **xyz** is used below as a placeholder for the name of your instance.

Source code setup
-----------------

Clone the GitHub repo. The commands below use the base GitHub repo;
substitute by whichever fork you are using.

    $ cd /var/www/apps
    $ sudo -u nginx mkdir xyz
    $ cd xyz
    $ sudo -u nginx git clone https://github.com/pekrau/OrderPortal.git

Create the subdirectory for your instance using the `site` template:

    $ cd OrderPortal/orderportal
    $ sudo -u nginx cp -r site xyz

The files in your `xyz` directory most likely need to be modified.
In particular, the YAML files may need to be adjusted or replaced.

Download and install the required third-party Python modules using the
`requirements.txt` file. Whether you should do this as `root` or some other
user depends on the policy at your site.

    $ sudo pip install -r requirements.txt

Settings file
-------------

Create the settings file and edit its contents according to your instance.
Some of the settings depend on actions described below.

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
    secret password. This password must also be edited into the settings file.
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
    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python2 init_database.py

Create the first admin account in the database by running a script that
will interactively ask for input:

    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python2 create_admin.py

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
[orderportal/site/orderportal_xyz.service](orderportal/site/orderportal_xyz.service). Copy, rename and edit it.

    $ cd /etc/systemd/system
    $ sudo cp /var/www/apps/ddd/OrderPortal/orderportal/site/orderportal_xyz.service orderportal_ddd.service
    $ sudo emacs orderportal_ddd.service

HTTP nginx configuration
------------------------

In our case, the tornado server is made available by reverse-proxy
through nginx. The template nginx file is available at
[orderportal/site/orderportal_xyz.conf](orderportal/site/orderportal_xyz.conf).
Copy, rename and edit it. In particular, ensure that the URL and port is
specified correctly.

    $ cd /etc/nginx/conf.d
    $ sudo cp /var/www/apps/ddd/OrderPortal/orderportal/site/orderportal_xyz.conf orderportal_ddd.conf

Backup
------

Backup relies on running a script to dump all data in the CouchDB database
to a tar file. Create a backup directory:

    $ sudo mkdir /home/backup/backup_files/orderportal_xyz

Copy, rename and edit the template bash backup script
[orderportal/site/dump_orderportal_xyz.bash](orderportal/site/dump_orderportal_xyz.bash):

    $ cd /var/www/apps/xyz/OrderPortal/orderportal/site
    $ sudo cp dump_orderportal_xyz.bash /etc/scripts/dump_orderportal_xyz.bash

The line in the crontab file should be something like this:

45 22 * * * /etc/scripts/dump_orderportal_xyz.bash

Maintenance, updates
--------------------

To update the source code from the GitHub repo:

    $ cd /var/www/apps/xyz/OrderPortal
    $ sudo -u nginx git pull
    $ sudo systemctl restart orderportal_xyz

To load any new CouchDB design documents (i.e. index definitions):

    $ cd /var/www/apps/xyz/OrderPortal/orderportal
    $ sudo -u nginx PYTHONPATH=/var/www/apps/xyz/OrderPortal python2 load_designs.py

Unless the OrderPortal app is running in debug mode, the tornado server
will have to be restarted.

    $ sudo systemctl restart orderportal_xyz.service
