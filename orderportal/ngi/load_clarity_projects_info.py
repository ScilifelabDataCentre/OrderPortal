"""Load information from projects in Clarity LIMS to their corresponding orders.
Relies on the order id being present in the LIMS as a UDF called "Portal ID".
Sets Project_ID (as tag), Project_name (as tag), status, status history.

This is specific to the Clarity LIMS configuration for NGI Stockholm,
so it will at the very least have to be modified for your setup.
However, it might prove useful as a starting point.
"""

from __future__ import print_function, absolute_import

import copy
import sys
import urlparse
from xml.etree import ElementTree

# Requires these third-party Python packages
import requests
import yaml

from orderportal import settings
from orderportal import utils
from orderportal.order import OrderSaver


NSMAP = dict(
    artgr='http://genologics.com/ri/artifactgroup',
    art='http://genologics.com/ri/artifact',
    cnf='http://genologics.com/ri/configuration',
    con='http://genologics.com/ri/container',
    ctp='http://genologics.com/ri/containertype',
    exc='http://genologics.com/ri/exception',
    file='http://genologics.com/ri/file',
    inst='http://genologics.com/ri/instrument',
    lab='http://genologics.com/ri/lab',
    prc='http://genologics.com/ri/process',
    prj='http://genologics.com/ri/project',
    prx='http://genologics.com/ri/processexecution',
    ptm='http://genologics.com/ri/processtemplate',
    ptp='http://genologics.com/ri/processtype',
    res='http://genologics.com/ri/researcher',
    ri='http://genologics.com/ri',
    rtp='http://genologics.com/ri/reagenttype',
    smp='http://genologics.com/ri/sample',
    udf='http://genologics.com/ri/userdefined',
    ver='http://genologics.com/ri/version')

for prefix, url in NSMAP.iteritems():
    ElementTree._namespace_map[url] = prefix


class Clarity(object):

    def __init__(self):
        # Will crash if not set; that is appropriate.
        clarity_settings = settings['CLARITY_LIMS']
        self.session = requests.Session()
        self.session.auth = (clarity_settings['USERNAME'],
                             clarity_settings['PASSWORD'])
        self.session.headers.update({'headers': {'Accept':'application/xml'}})
        self.resources = {}
        response = self.session.get(clarity_settings['API_URL'])
        if response.status_code != 200:
            raise IOError("HTTP status code %s" % response.status_code)
        etree = ElementTree.fromstring(response.content)
        for element in etree.findall('link'):
            self.resources[element.get('rel')] = element.get('uri')

    def get_all_projects(self):
        """Get list of records for all projects in the LIMS.
        Each record is a dictionary containing 'url',  'lims_id' 
        and 'project_name'.
        """
        result = []
        url = self.resources['projects']
        params = {}
        while True:
            response = self.session.get(url, params=params)
            if response.status_code != 200:
                raise IOError("HTTP status code %s" % response.status_code)
            etree = ElementTree.fromstring(response.content)
            for element in etree.findall('project'):
                elem = element.find('name')
                record = dict(uri=element.get('uri'),
                              lims_id=element.get('limsid'),
                              project_name=elem.text)
                result.append(record)
            element = etree.find('next-page')
            if element is None: break
            parts = urlparse.urlparse(element.get('uri'))
            params = dict(urlparse.parse_qsl(parts.query))
        return result

    def fetch_project_info(self, record):
        """Get information for the project and add to the record.
        Most of this information depends on the specific configuration
        of the LIMS instance."""
        response = self.session.get(record['uri'])
        if response.status_code != 200:
            raise IOError("HTTP status code %s" % response.status_code)
        etree = ElementTree.fromstring(response.content)
        element = etree.find('open-date') # processing
        if element is not None:
            record['open-date'] = element.text
        element = etree.find('close-date') # closed
        if element is not None:
            record['close-date'] = element.text
        udfs = etree.findall('{%s}field' % NSMAP['udf'])
        for key in ['Portal ID',
                    'Order received', # submitted
                    'Contract sent', # accepted
                    'Contract received', # accepted
                    'Plates sent', # accepted
                    'Samples received', # processing
                    'Sample information received', # processing
                    'Queued', # processing
                    'All raw data delivered', # closed
                    'Best Practice Analysis Completed', # closed
                    'Aborted', # aborted
                    ]:
            for udf in udfs:
                if udf.get('name') == key:
                    record[key.lower().replace(' ', '_')] = udf.text
        try:
            portal_id = record['portal_id']
        except KeyError:
            pass
        else:
            try:
                value = int(portal_id)                
            except ValueError:
                if not portal_id.upper().startswith('NGI'):
                    del record['portal_id']
            else:
                record['portal_id'] = 'NGI{0:=05d}'.format(value)

def get_orders(db, statuses=[]):
    """Get all orders in CouchDB having a 'identifier' field.
    Return a lookup with 'identifier' as key.
    If 'statuses' is given, then only return orders with one of those.
    """
    result = {}
    for row in db.view('order/modified', include_docs=True):
        doc = row.doc
        if statuses:
            if doc['status'] not in statuses: continue
        identifier = doc.get('identifier')
        if not identifier: continue
        result[identifier] = doc
    return result

def process_project(db, project, orders_lookup, dryrun=False):
    """Process the Clarity project:
    1) Find corresponding order.
    2) Set the tags, if not done.
    3) Set the status history.
    4) Set the current status.
    """
    try:
        portal_id = project['portal_id']
    except KeyError:
        return
    try:
        order = orders_lookup[portal_id]
    except KeyError:
        print('Warning: could not find order', portal_id)
        return
    changed = False

    old_tags = set(order.get('tags', []))
    tags = old_tags.union(["Project_ID:%s" % project['lims_id'],
                           "Project_name:%s" % project['project_name']])
    changed = old_tags != tags

    current = None
    processing = [project.get('samples received'),
                  project.get('sample information received'),
                  project.get('queued')]
    processing = [p for p in processing if p is not None]
    if processing:
        processing = reduce(min, processing)
        if processing:
            current = 'processing'
            date = processing
            if processing > order['history'].get('processing'):
                changed = True
            else:
                processing = False

    closed = [project.get('close-date'),
              project.get('all raw data delivered'),
              project.get('best practice analysis completed')]
    closed = [c for c in closed if c is not None]
    if closed:
        closed = reduce(min, closed)
        if closed:
            current = 'closed'
            date = closed
            if closed > order['history'].get('closed'):
                changed = True
            else:
                closed = False

    aborted = project.get('aborted')
    if aborted:
        current = 'aborted'
        date = aborted
        if aborted > order['history'].get('aborted'):
            changed = True
        else:
            aborted = False

    if current and current != order.get('status'):
        changed = True
    else:
        current = False
    
    if changed:
        if dryrun:
            print('Would have updated information for', portal_id)
        else:
            old_order = copy.deepcopy(order)
            with OrderSaver(doc=order, db=db) as saver:
                saver['tags'] = sorted(tags)
                if processing:
                    saver['history']['processing'] = processing
                if closed:
                    saver['history']['closed'] = closed
                if aborted:
                    saver['history']['aborted'] = aborted
                # Required to record the change in the log.
                if saver['history'] != old_order['history']:
                    saver.changed['history'] = saver['history']
                if current:
                    # Using the call 'set_status' ensures that a message is
                    # generated for sending to the user, when so configured.
                    saver.set_status(current, date=date)
            print('Updated information for', portal_id)

def regenerate_view(db, viewname):
    "Trigger CouchDB to regenerate the view by accessing it."
    view = db.view(viewname)
    for row in view:
        break

if __name__ == '__main__':
    print(utils.now())
    parser = utils.get_command_line_parser(description=
        'Load project info from Clarity LIMS into OrderPortal.')
    parser.add_option('-d', '--dryrun',
                      action="store_true", dest="dryrun", default=False,
                      help='dry run: no changes stored')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings)

    db = utils.get_db()
    orders_lookup = get_orders(db)

    clarity = Clarity()
    clarity_projects = clarity.get_all_projects()

    for project in clarity_projects:
        clarity.fetch_project_info(project)
        process_project(db, project, orders_lookup, dryrun=options.dryrun)
    regenerate_view(db, 'order/status')
    regenerate_view(db, 'order/tag')
