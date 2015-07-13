"OrderPortal: Load all CouchDB database design documents."

from __future__ import print_function, absolute_import

import sys

from orderportal import utils


def get_args():
    parser = utils.get_command_line_parser(description=
        'Reload all CouchDB design documents.')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    utils.load_designs(utils.get_db(),
                       verbose=options.verbose)
