" OrderPortal: Load the users from a JSON dump from the old Drupal site."

from __future__ import print_function, absolute_import

import json
import collections
import pprint

from orderportal import constants
from orderportal import settings
from orderportal import utils

UNI_LOOKUP = dict(
    karolinska='KI',
    uppsala='UU',
    uppsalas='UU',
    uppmax='uu',
    umea='UMU',
    goteborgs='GU',
    goteborg='GU',
    gothenburg='GU',
    stockholms='SU',
    stockholm='SU',
    lund='LU',
    lunds='LU',
    chalmers='CTH',
    linkopings='LIU',
    linkoping='LIU',
    orebro='ORU',
    sodertorn='SH',
    linneuniversitetet='LNU',
    linnaeus='LNU',
)
UNI_LOOKUP['swedish university of agricultural sciences'] = 'SLU'
UNI_LOOKUP['swedish university of agricultural science'] = 'SLU'
UNI_LOOKUP['sveriges lantbruksuniversitet'] = 'SLU'
UNI_LOOKUP['university of gothenburg'] = 'GU'

def get_args():
    parser = utils.get_command_line_parser(description=
        'Load the users from the JSON dump from the old Drupal site.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default='dump.json',
                      metavar="FILE", help="filepath of dump file to load")
    return parser.parse_args()

def load_users(verbose=False, dumpfilepath=None):
    db = utils.get_db()
    users = json.load(open(dumpfilepath))
    if verbose:
        print(len(users), 'users in input file')
    count = 0
    for user in users:
        email = user['mail']
        docs = [r.doc
                for r in db.view('user/email', include_docs=True, key=email)]
        if len(docs) > 0:
            if verbose:
                print(email, 'exists already; skipped')
            continue
        status = user['status']
        if status != '1':
            if verbose:
                print(email, 'status', status, '; skipped')
            continue
        first_name = user['field_user_address'].get('first_name')
        last_name = user['field_user_address'].get('last_name')
        roles = set(user['roles'])
        role = roles.difference(set([2])) and constants.ADMIN or constants.USER
        address = []
        street = user['field_user_address'].get('thoroughfare')
        if street:
            address.append(street)
        locality = user['field_user_address'].get('locality')
        postal_code = user['field_user_address'].get('postal_code')
        postal = [postal_code, locality]
        postal = ' '.join([p for p in postal if p])
        if postal:
            address.append(postal)
        address.append(user['field_user_address'].get('country') or 'SE')
        address = '\n'.join(address)
        premise = user['field_user_address'].get('premise')
        university = user['field_user_address'].get('organisation_name')
        university = ' '.join(university.strip().split())
        uni = utils.to_ascii(university.replace(',', ''))
        try:
            uni = uni.split()[0]
        except IndexError:
            university = '[unknown]'
        else:
            if uni.upper() not in settings['UNIVERSITY_LIST']:
                try:
                    uni = UNI_LOOKUP[uni.lower()]
                    university = uni
                except KeyError:
                    try:
                        uni = UNI_LOOKUP[university.lower()]
                        university = uni
                    except KeyError:
                        pass
                        # if verbose:
                        #     print(university)
        other = []
        try:
            other.append("user id: {}".format(user['uid']))
        except KeyError:
            pass
        try:
            other.append("user name: {}".format(user['name']))
        except KeyError:
            pass
        other = '\n'.join(other)

        doc = collections.OrderedDict()
        doc['_id'] = utils.get_iuid()
        doc[constants.DOCTYPE] = constants.USER
        doc['email'] = email
        doc['role'] = role
        doc['password'] = None
        doc['first_name'] = first_name
        doc['last_name'] = last_name
        doc['university'] = university
        doc['department'] = premise
        doc['address'] = address
        doc['other'] = other
        doc['owner'] = email
        doc['created'] = utils.timestamp()
        doc['modified'] = utils.timestamp()
        doc['status'] = constants.DISABLED
        if verbose:
            for key, value in doc.items():
                print(key, ':', value)
            print()
        db.save(doc)

        count += 1
        if count > 1: break
    if verbose:
        print(count, 'users loaded')

if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    load_users(dumpfilepath=options.FILE,
               verbose=options.verbose)
