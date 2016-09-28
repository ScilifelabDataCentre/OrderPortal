"OrderPortal: File test processors."

from __future__ import print_function, absolute_import

from orderportal.utils import BaseProcessor


class TextFile(BaseProcessor):
    "The value must be a text file."

    def run(self, value, **kwargs):
        try:
            if kwargs['content_type'] != 'text/plain':
                raise ValueError('value is not a text file')
        except KeyError:
            raise ValueError('value is not a file')
