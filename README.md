OrderPortal
===========

The OrderPortal system is a web-based portal that allows form-based
submission of information from users to a facility. It was designed
academic service facilities that handle discrete orders or project
proposals, reports, etc, from its researcher users. It has also been
used as a system to gather reports from researchers and research
units.

The documentation of the features of the system are available at the
URL `/documentation` in a running OrderPortal instance, e.g. in
the demo instance at
[https://orderportal.scilifelab.se/](https://orderportal.scilifelab.se/)


## Installation

The current version has been developed using Python 3.10 or higher.
It may work on Python 3.8 and 3.9, but this has not been tested.

### Settings file

From version 11.0 of OrderPortal, it is possible to use only environment
variables for the basic configuration of the system. All other configurations
have been moved into the database, and can be modified using the web interface.

However, it is still possible to use a YAML settings file for the basic configuration.
On startup, the OrderPortal system looks for a YAML settings file first by the
file path given by the environment variable ORDERPORTAL_SETTINGS_FILEPATH, and
in second place by the file path `OrderPortal/site/settings.yaml`. The first of
these files found, if any, will be used.

If both an environment variable and an entry in a YAML settings file defines
a configuration value, then the environment variable takes precedence.

See the comments in the template file
`OrderPortal/settings_template.yaml` file for editing the file for
your site. In particular, the CouchDB variables must be set (see
below).

### Docker containers

Docker containers for the releases can be retrieved from
[ghcr.io/scilifelabdatacentre](ghcr.io/scilifelabdatacentre/orderportal).


### Development Setup

When developing, we recommend that you run the application locally using Docker.

#### Start services

```bash
docker-compose up
```

This command will orchestrate the building and running of the application, the couchDB database and a local mail server called mailcatcher

#### Check services

The setup consists of the following services:

1. **CouchDB**  
   - A NoSQL database for storing data.  
   - Accessible locally at `http://127.0.0.1:5984/_utils/index.html`.  
   - Username and password are defined in the .env file

2. **OrderPortal**  
   - A Python-based web application with Tornado framework.  
   - Accessible locally on:  
     - Web interface: `http://127.0.0.1:8880`  
   - Depends on CouchDB for database storage.  

3. **MailCatcher**  
   - A local SMTP server for catching test emails.  
   - Accessible at `http://127.0.0.1:1080` for viewing emails.  

#### Create first admin

Enter the backend container and create the first admin user:

```bash
docker exec -it orderportal python cli.py create-admin test@test.se --password test_password
```

You need to input a Name and University for this user. Once done, go to the web interface at `http://127.0.0.1:8880` and log in.

#### Developing

Your local files in /orderportal directory are automatically synchronized with the container running the orderportal, so you can edit files using your favorite editor and then test them.
Sometimes, for some changes you would need to restart the service anyway. If you encounter any issue re-running the containers, you can force a clean re-start with:

```bash
docker-compose down --rmi all -v --remove-orphans && docker-compose up
```


### From source code

This instruction is based on the **old** procedure used previously for the
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

#### CouchDB setup

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

#### `Tornado` server

The `tornado` server should be executed as a system service. This depends
on your operating system; refer to its documentation.

It is recommended that you use a reverse proxy for the `tornado`
server, e.g. `nginx` or `apache`. See the documentation for those
systems.

#### Updates

To update the source code, simply download the latest release, unpack
the `tar.gz` file, and move the `OrderPortal` directory tree to the
correct location.  Ensure that you keep your `site` directory, and
that it is placed in the same location as before.

Since OrderPortal version 3.6.19, the CouchDB design documents (which
define the database indexes) are automatically updated when the
`tornado` server is restarted.
