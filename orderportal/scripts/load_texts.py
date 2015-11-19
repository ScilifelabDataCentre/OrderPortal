"OrderPortal: Load texts from file into the database."

from __future__ import print_function, absolute_import

import sys

import yaml

from orderportal import settings
from orderportal import utils
from orderportal import admin


def load_texts(db, textfilepath=None, verbose=False):
    if textfilepath is None:
        if settings.get('SITE_DIR'):
            textfilepath = utils.expand_filepath('{SITE_DIR}texts.yaml')
        else:
            textfilepath = utils.expand_filepath('{ROOT}data/texts.yaml')
    with open(utils.expand_filepath(textfilepath)) as infile:
        texts = yaml.safe_load(infile)
        for key, text in texts.items():
            docs = [r.doc for r
                    in db.view('text/name', include_docs=True, key=key)]
            try:
                doc = docs[0]
            except IndexError:
                doc = None
            with admin.TextSaver(doc=doc, db=db) as saver:
                saver['name'] = key
                saver['text'] = text
            if verbose:
                print("Text '{0}' loaded".format(key))


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        'Load texts from file into the database.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    if not options.force:
        response = raw_input('about to overwrite all current texts; really sure? [n] > ')
        if not utils.to_bool(response):
            sys.exit('aborted')
    try:
        textfilepath = args[0]
    except IndexError:
        textfilepath = None
    load_texts(utils.get_db(),
               textfilepath=textfilepath,
               verbose=options.verbose)
