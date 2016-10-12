"OrderPortal: Base class for order field value processor framework."


class BaseProcessor(object):
    """Abstract vase class for processor classes.
    Implement the 'run' method, which should raise a ValueError
    if there is something wrong with the value.
    """

    def __init__(self, db, order, field):
        self._db = db
        self._order = order
        self._field = field
        self.initialize()

    def initialize(self):
        "Override to initialize instance."
        pass

    @property
    def db(self):
        return self._db

    @property
    def order(self):
        return self._order

    @property
    def field(self):
        return self._field

    def run(self, value, **kwargs):
        """Implement this method.
        Raise ValueError when something is wrong with the value."""
        raise NotImplementedError
