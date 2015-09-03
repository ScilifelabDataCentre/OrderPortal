"OrderPortal: Load texts from file into the database."

from __future__ import print_function, absolute_import

import sys

import yaml

from orderportal import utils


def load_texts(textfilepath):
    try:
        with open(utils.expand_filepath(textfilepath)) as infile:
            texts = yaml.safe_load(infile)
        except IOError:
            pass
        else:
            for text in texts:
                with home.TextSaver(db=db) as saver:
                    # XXX
                    pass


def get_args():
    parser = utils.get_command_line_parser(description=
        'Load texts from file into the database.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default='../data/texts.yaml',
                      metavar="FILE", help="filepath of texts file to load")
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    utils.load_texts(utils.get_db(),
                     textfilepath=options.FILE,
                     verbose=options.verbose)
