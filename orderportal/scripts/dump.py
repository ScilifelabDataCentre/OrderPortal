#!/usr/bin/python2.7
""" PolyCentric: Dump the database into a JSON file.
The settings file may be given as the first command line argument,
otherwise it is obtained as usual.
The dump file will be called 'dump_{ISO date}.tar.gz' using today's date.
Create the dump file in the directory specified by BACKUP_DIR variable
in the settings, otherwise in the current working directory.
"""

import os
import sys
import time

from polycentric import settings
from polycentric import utils


if __name__ == '__main__':
    try:
        filepath = sys.argv[1]
    except IndexError:
        filepath = None
    utils.load_settings(filepath=filepath)
    db = utils.get_db()
    filepath = "dump_{}.tar.gz".format(time.strftime("%Y-%m-%d"))
    try:
        filepath = os.path.join(settings['BACKUP_DIR'], filepath)
    except KeyError:
        pass
    utils.dump(db, filepath)
