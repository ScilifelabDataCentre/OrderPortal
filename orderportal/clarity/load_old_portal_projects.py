"Clarity LIMS interface. Check contact."

from __future__ import print_function, absolute_import

import urlparse
from xml.etree import ElementTree

import requests
import yaml

from orderportal import settings
from orderportal import utils


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
        with open('settings.yaml') as infile:
            clarity_settings = yaml.safe_load(infile)
        self.API_URL = clarity_settings['API_URL']
        self.session = requests.Session()
        self.session.auth = (clarity_settings['USERNAME'],
                             clarity_settings['PASSWORD'])
        self.session.headers.update({'headers': {'Accept':'application/xml'}})
        self.resources = {}
        response = self.session.get(self.API_URL)
        assert response.status_code == 200
        etree = ElementTree.fromstring(response.content)
        for element in etree.findall('link'):
            self.resources[element.get('rel')] = element.get('uri')

    def get_all_projects(self, verbose=False):
        """Get list of records for all projects in the LIMS.
        Each record is a dictionary containing 'url',  'lims_id' 
        and 'project_name'.
        """
        result = []
        url = self.resources['projects']
        params = {}
        while True:
            if verbose:
                print('getting', url, sorted(params.items()))
            response = self.session.get(url, params=params)
            assert response.status_code == 200
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

    def fetch_project_info(self, record, verbose=True):
        "Get information for the project and add to the record."
        if verbose:
            print('getting', url)
        response = self.session.get(record['uri'])
        assert response.status_code == 200
        # with open("{0}.xml".format(record['lims_id']), 'w') as outfile:
        #     outfile.write(response.content)
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
                    record[key.lower()] = udf.text
        try:
            value = int(record.pop('portal id'))
        except (KeyError, ValueError, TypeError):
            pass
        else:
            record['nid'] = str(value)

def get_old_portal_projects(db):
    """Get all projects in the database having a 'nid' field which
    are not closed or aborted. Return a lookup with 'nid' as key.
    """
    result = {}
    for row in db.view('order/modified', include_docs=True):
        doc = row.doc
        if doc['status'] in ('closed', 'aborted'): continue
        nid = doc['fields'].get('nid')
        if not nid: continue
        result[nid] = doc
    return result

def process_old_portal_projects(db, projects, clarity_lookup, verbose=False):
    """Process the project from the old portal which are not closed or aborted.
    Get info on each from the Clarity lookup, and add the values.
    """
    for project in projects:
        changed = False
        cp = clarity_lookup.get(project['fields']['nid'])
        if not cp: continue
        if project['fields'].get('project_name') != cp.get('project_name'):
            project['fields']['project_name'] = cp['project_name']
            changed = True
        if project['fields'].get('lims_id') != cp.get('lims_id'):
            project['fields']['lims_id'] = cp['lims_id']
            changed = True
        # Map Clarity dates to milestones as best as possible.
        # XXX This must be reviewed!
        submitted = cp.get('order received')
        if submitted and submitted != project['milestones'].get('submitted'):
            project['milestones']['submitted'] = submitted
            changed = True
        accepted = [cp.get('contract sent'),
                    cp.get('contract received'),
                    cp.get('plates sent')]
        accepted = [a for a in accepted if a is not None]
        if accepted:
            accepted = reduce(min, accepted)
            if accepted and accepted != project['milestones'].get('accepted'):
                project['milestones']['accepted'] = accepted
                changed = True
        processing = [cp.get('samples received'),
                      cp.get('sample information received'),
                      cp.get('queued')]
        processing = [p for p in processing if p is not None]
        if processing:
            processing = reduce(min, processing)
            if processing and processing != project['milestones'].get('processing'):
                project['milestones']['processing'] = processing
                changed = True
        closed = [cp.get('close-date'),
                  cp.get('all raw data delivered'),
                  cp.get('best practice analysis completed')]
        closed = [c for c in closed if c is not None]
        if closed:
            closed = reduce(min, closed)
            if closed and closed != project['milestones'].get('closed'):
                project['milestones']['closed'] = closed
                changed = True
        aborted = cp.get('aborted')
        if aborted and aborted != project['milestones'].get('aborted'):
            project['milestones']['aborted'] = aborted
            changed = True
        current = None
        for status in settings['ORDER_STATUSES']:
            if status['identifier'] == 'undefined': continue
            if project['milestones'].get(status['identifier']):
                current = status['identifier']
        if current != project.get('status'):
            project['status'] = current
            changed = True
        if len(project['milestones']) > 2:
            try:
                del project['milestones']['undefined']
            except KeyError:
                pass
            else:
                changed = True
        if changed:
            if verbose:
                print('saving',
                      project['fields']['nid'],
                      project['fields']['lims_id'],
                      project['status'],
                      project['title'])
            db.save(project)
        else:
            if verbose:
                print('no change for', project['fields']['nid'])


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        'Load project info from Clarity LIMS into OrderPortal.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)

    db = utils.get_db()
    projects_lookup = get_old_portal_projects(db)
    print(len(projects_lookup), 'projects from old portal requiring more info')
    projects = projects_lookup.values()
    projects.sort(lambda i,j: cmp(i['modified'], j['modified']))
    if options.verbose:
        for project in projects:
            print(project['fields']['nid'], project['modified'])

    clarity = Clarity()
    clarity_projects = clarity.get_all_projects(verbose=options.verbose)
    print(len(clarity_projects), 'projects in Clarity')
    for record in clarity_projects:
        clarity.fetch_project_info(record, verbose=options.verbose)
        print(record['lims_id'], 'nid', record.get('nid'))

    clarity_lookup = {}
    for p in clarity_projects:
        nid = p.get('nid')
        if nid: clarity_lookup[nid] = p
    print(len(clarity_lookup), 'projects from Clarity')

    process_old_portal_projects(db,
                                projects,
                                clarity_lookup,
                                verbose=options.verbose)
