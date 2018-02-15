"OrderPortal: Check samples table value."

from __future__ import print_function, absolute_import

from orderportal.processors.table_check import TableCheck


class SamplesCheck(TableCheck):
    """Check a table with rows having columns:
    1) sampleid, must be unique
    2) index, must be non-blank
    3) concentration, must be a float value
    """

    def initialize(self):
        self.sampleids = set()

    def check_row(self, row):
        sampleid = row[0]
        if sampleid in self.sampleids:
            raise ValueError('duplicate sampleid')
        self.sampleids.add(sampleid)
        if not row[1]:
            raise ValueError('no index specified')
        try:
            float(row[2])
        except (ValueError, TypeError):
            raise ValueError('invalid concentration')
