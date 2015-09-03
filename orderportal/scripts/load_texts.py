"OrderPortal: Load texts from file into the database."

from __future__ import print_function, absolute_import

import sys

import yaml

from orderportal import utils
from orderportal import home


def load_texts(db, textfilepath, verbose=False):
    with open(utils.expand_filepath(textfilepath)) as infile:
        texts = yaml.safe_load(infile)
        for key, text in texts.items():
            docs = [r.doc for r
                    in db.view('text/name', include_docs=True, key=key)]
            try:
                doc = docs[0]
            except IndexError:
                doc = None
            with home.TextSaver(doc=doc, db=db) as saver:
                saver['name'] = key
                saver['text'] = text
            if verbose:
                print("Text '{}' loaded".format(key))

def get_args():
    parser = utils.get_command_line_parser(description=
        'Load texts from file into the database.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE',
                      default='{ROOT}/data/texts.yaml',
                      metavar="FILE", help="filepath of texts file to load")
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    load_texts(utils.get_db(),
               textfilepath=options.FILE,
               verbose=options.verbose)
