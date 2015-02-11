""" OrderPortal: Dump the database into a tar file.
The settings file may be given as the first command line argument,
otherwise it is obtained as usual.
The dump file will be called 'dump_{ISO date}.tar.gz' using today's date.
Create the dump file in the directory specified by BACKUP_DIR variable
in the settings, otherwise in the current working directory.
"""

from __future__ import unicode_literals, print_function, absolute_import

import os
import time

from orderportal import settings
from orderportal import utils


def get_command_line_parser():
    parser = utils.get_command_line_parser(description=
        'Dump all data into a tar file.')
    parser.add_option('-d', '--dumpfile',
                      action='store', dest='dumpfile',
                      metavar='DUMPFILE', help='name of dump file')
    return parser


if __name__ == '__main__':
    parser = get_command_line_parser()
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    if options.dumpfile:
        filepath = options.dumpfile
    else:
        filepath = "dump_{}.tar.gz".format(time.strftime("%Y-%m-%d"))
    try:
        filepath = os.path.join(settings['BACKUP_DIR'], filepath)
    except KeyError:
        pass
    utils.dump(db, filepath, verbose=options.verbose)
