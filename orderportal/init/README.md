This directory contains the script 'init_database.py' which is used
to initialize the OrderPortal database, and optionally load a dump file.

The CouchDB instance must already exist, and the account to connect
with it must have been created and defined in the settings file. This
script will clobber any existing data!

Each text in the file 'init_texts.yaml' is loaded unless it has already
been loaded from the dump file (if any).
