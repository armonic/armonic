from mss.common import IterContainer, DoesNotExist, ValidationError, ExtraInfoMixin
from mss.xml_register import XmlRegister

import logging
logger = logging.getLogger(__name__)


class Provide(IterContainer, XmlRegister, ExtraInfoMixin):
    """Basically, this describes a list of :py:class:`Require`."""
    def __init__(self, name=None, requires=[], flags={}, **extra):
        ExtraInfoMixin.__init__(self, **extra)
        self.name = name
        IterContainer.__init__(self, *requires)
        self.flags = flags  # Should not be in Requires ...

    def __call__(self, func):
        """
        Used as a method decorator mark :py:class:`State` methods
        as provide.
        """
        if not hasattr(func, '_requires'):
            func._requires = []
        return func

    def get_values(self):
        acc = {}
        for r in self:
            acc.update({r.name: r.get_values()})
        return acc

    def get_default_values(self):
        acc = {}
        for r in self:
            acc.update({r.name: r.get_default_values()})
        return acc

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        return self

    def _xml_ressource_name(self):
        return "provide"

    def require_by_name(self, require_name):
        """
        :param require_name: Require name
        :type require_name: str

        :rtype: :class:`Require`
        """
        return self.get(require_name)

    def fill(self, variables_values):
        """Fill the Provide with variables_values

        :param variables_values: list of tuple (variable_xpath, variable_values)
            variable_xpath is a full xpath
            variable_values is dict of index=value
        """
        def _filter_values(variables_values):
            # Return only variables for this Provide
            for xpath, values in variables_values:
                provide_name = XmlRegister.get_ressource(xpath, "provide")
                require_name = XmlRegister.get_ressource(xpath, "require")
                if not (provide_name == self.name and self.require_by_name(require_name)):
                    continue
                yield (xpath, values)

        for require in self:
            require.fill(_filter_values(variables_values))

    def validate(self):
        for require in self:
            logger.debug("Validating %s" % (require))
            try:
                require.validate()
            except ValidationError as e:
                e.require_name = require.name
                raise e

    def has_variable(self, variable_name):
        """Return True if variable_name is specified by this provide"""
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
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "requires": [r.to_primitive() for r in self],
                "flags": self.flags}

    def __repr__(self):
        return "<Provide:%s(%s,%s)>" % (self.name,
                                        IterContainer.__repr__(self),
                                        self.flags)


class Flags(object):

    def __init__(self, **flags):
        self.flags = dict(**flags)

    def __call__(self, func):
        if self.flags:
            func._flags = self.flags
        return Provide()(func)
