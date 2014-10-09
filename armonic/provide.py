import logging
import itertools
from time import time

from armonic.utils import IterContainer, DoesNotExist
from armonic.common import ValidationError, ExtraInfoMixin
from armonic.xml_register import XMLRegistery, XMLRessource


XMLRegistery = XMLRegistery()
logger = logging.getLogger(__name__)


class Provide(IterContainer, XMLRessource, ExtraInfoMixin):
    """Basically, this describes the method of a
    :class:`armonic.lifecycle.State`.

    It contains the list of :class:`armonic.require.Require` needed to
    call the method.

    :param name: name of the method
    :param requires: list of requires
    :param flags: flags to be propagated
    :param tags: a list of tags where tags are strings
    :type tags: list
    :param label: a human readable short description
    :param help: a long help message
    """
    _persist = True

    def __init__(self, name=None, requires=[], flags={}, **extra):
        XMLRessource.__init__(self)
        IterContainer.__init__(self, *requires)
        ExtraInfoMixin.__init__(self, **extra)
        self.name = name
        self.flags = flags

        # Last caller
        self.source = None
        self.history = ProvideHistory()

    def __call__(self, func):
        """Used as a method decorator mark state methods as provides.

        TODO: Check if provide properties (name, label, help, ...) are
        defined several times.
        """
        if not hasattr(func, '_provide'):
            func._provide = self
        func._provide.name = func.__name__
        func._provide.flags.update(self.flags)
        func._provide.extra.update(self.extra)
        for require in self:
            if require not in func._provide:
                func._provide.append(require)
        return func

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        return self

    def _xml_ressource_name(self):
        return "provide"

    def _persist_primitive(self):
        return self.history.to_primitive()

    def _persist_load_primitive(self, history):
        if history is not None:
            self.history = ProvideHistory(initial_history=history)

    def require_by_name(self, require_name):
        """
        :param require_name: require name
        :type require_name: str

        :rtype: :class:`armonic.require.Require`
        """
        return self.get(require_name)

    def fill(self, requires=[]):
        """Fill the provide with variables values.

        :param variables_values: list of tuple (variable_xpath, variable_values)::

            ("//xpath/to/variable", {0: value}),
            ("//xpath/to/variable", {0: value})
        """
        def _filter_values(variables_values):
            # Return only variables for this Provide
            for xpath, values in variables_values:
                for xpath_abs in XMLRegistery.find_all_elts(xpath):
                    provide_name = XMLRegistery.get_ressource(xpath_abs, "provide")
                    if not provide_name == self.name:
                        continue
                    require_name = XMLRegistery.get_ressource(xpath_abs, "require")
                    try:
                        self.require_by_name(require_name)
                    except DoesNotExist:
                        continue
                    yield (xpath_abs, values)

        if not requires:
            return

        variables_values = list(_filter_values(requires[0]))
        for require in self:
            require.fill(variables_values)
        try:
            self.source = requires[1]
        except IndexError:
            self.source = None

    def validate(self):
        """Validate the provide.

        :raises ValidationError: when validation fails
        """
        for require in self:
            logger.debug("Validating %s" % (require))
            try:
                require.validate()
            except ValidationError as e:
                logger.debug("Validation error on provide '%s'" % self.get_xpath())
                e.require_name = require.name
                raise e

    def has_variable(self, variable_name):
        for r in self:
            try:
                r.variables().get(variable_name)
                return True
            except DoesNotExist:
                pass
        return False

    def get_all_variables(self):
        acc = []
        for r in self:
            for v in r._variables:
                acc.append(v.name)
        return acc

    def to_primitive(self):
        """Serialize the provide to a python dict.
        """
        primitive = ExtraInfoMixin.to_primitive(self)
        primitive.update({
            "name": self.name,
            "xpath": self.get_xpath_relative(),
            "requires": [r.to_primitive() for r in self],
            "flags": self.flags
        })
        return primitive

    def get_values(self):
        source = self.source
        if self.source is None:
            source = {}
        return [list(itertools.chain(*[r.get_values() for r in self])), source]

    def _clear(self):
        """Reset variables to default values in all reauires.
        """
        for r in self:
            r._clear()

    def finalize(self):
        # record call
        self.history.add_entry(requires=self.get_values())
        # clear provide
        self._clear()

    def __repr__(self):
        return "<Provide:%s(%s,flags=%s)>" % (self.name,
                                              IterContainer.__repr__(self),
                                              self.flags)


class Flags(object):
    """Decorator to define flags on a state method.
    """
    def __init__(self, **flags):
        self.flags = dict(**flags)

    def __call__(self, func):
        return Provide(name=None, requires=[], flags=self.flags)(func)


class ProvideHistory(object):
    """Record provide calls.
    """

    def __init__(self, initial_history=[]):
        self._history = initial_history

    def add_entry(self, requires=[]):
        self._history.append({'timestamp': int(time()),
                              'requires': requires})

    def to_primitive(self):
        return self._history

    def last_entry(self):
        try:
            return self._history[-1]
        except IndexError:
            return None
