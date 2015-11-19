""" OrderPortal: Load accounts from JSON dump from the old Drupal site.
If an account already exists (based on email address), then no new data
for it is loaded.
"""

from __future__ import print_function, absolute_import

import datetime
import json
import collections
import pprint

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts.load_designs import regenerate_views


UNI_LOOKUP = dict(
    karolinska='KI',
    uppsala='UU',
    uppmax='UU',
    umea='UMU',
    goteborgs='GU',
    goteborg='GU',
    gothenburg='GU',
    stockholms='SU',
    stockholm='SU',
    kungliga='KTH',
    lund='LU',
    lunds='LU',
    chalmers='CTH',
    linkopings='LIU',
    linkoping='LIU',
    orebro='ORU',
    sodertorn='SH',
    linneuniversitetet='LNU',
    linnaeus='LNU',
    lantbruksuniversitetet='SLU',
    lantbruksuniversitet='SLU',
    lantbruks='SLU',
    agricultural='SLU',
    naturhistoriska='NRM',
)
UNI_LOOKUP['swedish university of agricultural sciences'] = 'SLU'
UNI_LOOKUP['swedish university of agricultural science'] = 'SLU'
UNI_LOOKUP['sveriges lantbruksuniversitet'] = 'SLU'
UNI_LOOKUP['university of gothenburg'] = 'GU'


def load_accounts(db, filepath='users.json', verbose=False):
    with open(filepath) as infile:
        accounts = json.load(infile)
    if verbose:
        print(len(accounts), 'accounts in input file')
    count = 0
    for account in accounts:
        email = account['mail'].lower()
        docs = [r.doc
                for r in db.view('account/email', include_docs=True, key=email)]
        if len(docs) > 0:
            if verbose:
                print(email, 'exists already; skipped')
            continue
        status = account['status']
        if status != '1':
            if verbose:
                print(email, 'status', status, '; skipped')
            continue
        first_name = account['field_user_address'].get('first_name')
        last_name = account['field_user_address'].get('last_name')
        roles = set(account['roles'])
        role = roles.difference(set([2])) and constants.ADMIN or constants.USER
        address = []
        street = account['field_user_address'].get('thoroughfare')
        if street:
            address.append(street)
        locality = account['field_user_address'].get('locality')
        postal_code = account['field_user_address'].get('postal_code')
        postal = [postal_code, locality]
        postal = ' '.join([p for p in postal if p])
        if postal:
            address.append(postal)
        address.append(account['field_user_address'].get('country') or 'SE')
        address = '\n'.join(address)
        premise = account['field_user_address'].get('premise')
        university = account['field_user_address'].get('organisation_name')
        university = ' '.join(university.replace(',', ' ').strip().split())
        uni = utils.to_ascii(university)
        try:
            uni = uni.split()[0]
        except IndexError:
            university = None
        else:
            if uni.upper() not in settings['UNIVERSITIES']:
                try:
                    university = UNI_LOOKUP[uni.lower()]
                except KeyError:
                    university_lower = university.lower()
                    try:
                        university = UNI_LOOKUP[university_lower]
                    except KeyError:
                        for uni in UNI_LOOKUP:
                            if uni in university_lower:
                                university = UNI_LOOKUP[uni]
                                break
        other_data = []
        try:
            other_data.append(u"old portal name: {0}".format(account['name']))
        except KeyError:
            pass
        try:
            other_data.append(u"old portal uid: {0}".format(account['uid']))
        except KeyError:
            pass
        other_data = '\n'.join(other_data)

        if verbose and university not in settings['UNIVERSITIES']:
            print(email, ':', university)
        doc = collections.OrderedDict()
        doc['_id'] = utils.get_iuid()
        doc[constants.DOCTYPE] = constants.ACCOUNT
        doc['email'] = email
        doc['role'] = role
        doc['password'] = None
        doc['first_name'] = first_name
        doc['last_name'] = last_name
        doc['university'] = university
        doc['department'] = premise
        doc['address'] = address
        doc['other_data'] = other_data
        doc['owner'] = email
        doc['created'] = utils.epoch_to_iso(account['created'])
        doc['modified'] = utils.epoch_to_iso(account.get('last_access') or account['created'])
        doc['status'] = constants.DISABLED
        if verbose:
            for key, value in doc.items():
                print(key, ':', value)
            print()
        db.save(doc)

        count += 1
    if verbose:
        print(count, 'accounts loaded')


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        "Load accounts from old Drupal site JSON dump 'users.json'.")
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    load_accounts(db, verbose=options.verbose)
    regenerate_views(db, verbose=options.verbose)
