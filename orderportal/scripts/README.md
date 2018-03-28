This directory contains a few stand-alone scripts for OrderPortal.

    dump.py

Dumps the entires contents of the CouchDB instance, except for the
design documents.

    messenger.py

This is the script which sends out email messages according to recent
modifications of accounts and orders. It should be executed in a
regular fashion by cron.
