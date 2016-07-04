"""Load status, Project_ID and Project_name to orders from
the corresponding projects in Clarity LIMS.

This is specific to the Clarity LIMS configuration for NGI Stockholm,
so it will at the very least have to be modified for your setup.
However, it might prove useful as a starting point.
"""

from __future__ import print_function, absolute_import

import sys
import urlparse
from xml.etree import ElementTree

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

    def __init__(self, verbose=False):
        self.verbose = verbose
        clarity_settings = settings.get('CLARITY_LIMS')
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
            if self.verbose:
                print('getting', url, sorted(params.items()))
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
        if self.verbose:
            print(len(result), 'projects from Clarity')
        return result

    def fetch_project_info(self, record):
        "Get information for the project and add to the record."
        if self.verbose:
            print('getting', record['uri'])
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

def process_project(db, project, orders_lookup, verbose=False):
    """Process the Clarity project:
    1) Find corresponding order.
    2) Set the tags, if not done.
    3) Set the status.
    4) Set the history.
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
    if verbose:
        print(portal_id, project['lims_id'], project['project_name'])
    old_tags = set(order.get('tags', []))
    new_tags = old_tags.union(["Project_ID:%s" % project['lims_id'],
                               "Project_name:%s" % project['project_name']])
    if old_tags != new_tags:
        with OrderSaver(doc=order, db=db) as saver:
            saver['tags'] = sorted(new_tags)
        print('Updated tags for', portal_id)

def regenerate_view(db, viewname):
    "Trigger CouchDB to regenerate the view by accessing it."
    view = db.view(viewname)
    for row in view:
        break

if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        'Load project info from Clarity LIMS into OrderPortal.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)

    db = utils.get_db()
    orders_lookup = get_orders(db)
    if options.verbose:
        print(len(orders_lookup), 'orders in OrderPortal')

    clarity = Clarity(verbose=options.verbose)
    clarity_projects = clarity.get_all_projects()

    for project in clarity_projects:
        clarity.fetch_project_info(project)
        process_project(db, project, orders_lookup, verbose=options.verbose)
    regenerate_view(db, 'order/tag')
