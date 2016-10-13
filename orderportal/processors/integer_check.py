"OrderPortal: Integer check processors."

from __future__ import print_function, absolute_import

from .baseprocessor import BaseProcessor


class PositiveInteger(BaseProcessor):
    "The value must be a positive integer."

    def run(self, value, **kwargs):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError('value is not an integer')
        if value <= 0:
            raise ValueError('value must be a positive integer')


class NonnegativeInteger(BaseProcessor):
    "The value must be a non-negative integer."

    def run(self, value, **kwargs):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError('value is not an integer')
        if value < 0:
            raise ValueError('value must be a non-negative integer')
