"OrderPortal: Add a to the database."

from __future__ import print_function, absolute_import

import sys

from orderportal import settings
from orderportal import utils
from orderportal import admin


def add_text(db, name, textfilepath, force=False, verbose=False):
    "Load the text from file, overwriting the current."
    with open(utils.expand_filepath(textfilepath)) as infile:
        text = infile.read()
        docs = [r.doc for r
                in db.view('text/name', include_docs=True, key=name)]
        try:
            doc = docs[0]
            if not force:
                sys.exit('text exists; not overwritten')
        except IndexError:
            doc = None
        with admin.TextSaver(doc=doc, db=db) as saver:
            saver['name'] = name
            saver['text'] = text
        if verbose:
            print("Text '{0}' loaded".format(name))


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        'Load a named text from file into the database.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    if len(args) != 2:
        sys.exit('Error: give name and filepath')
    add_text(utils.get_db(),
             name=args[0],
             textfilepath=args[1],
             force=options.force,
             verbose=options.verbose)
