#!/usr/bin/python2.7
"PolyCentric: Load all CouchDB database design documents."

from polycentric import utils


if __name__ == '__main__':
    utils.load_settings()
    utils.load_designs(utils.get_db())
