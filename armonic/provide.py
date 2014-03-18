import logging

from armonic.common import IterContainer, DoesNotExist, ValidationError, ExtraInfoMixin
from armonic.xml_register import XMLRegistery, XMLRessource


XMLRegistery = XMLRegistery()
logger = logging.getLogger(__name__)


class Provide(IterContainer, XMLRessource, ExtraInfoMixin):
    """Basically, this describes the method of a :class:`armonic.lifecycle.State`.

    It contains the list of :class:`armonic.require.Require` needed to call the method.

    :param name: name of the method
    :param requires: list of requires
    :param flags: flags to be propagated
    """
    def __init__(self, name=None, requires=[], flags={}, **extra):
        ExtraInfoMixin.__init__(self, **extra)
        self.name = name
        IterContainer.__init__(self, *requires)
        self.flags = flags  # Should not be in Requires ...

    def __call__(self, func):
        """Used as a method decorator mark state methods as provides.
        """
        if not hasattr(func, '_provide'):
            func._provide = self
        func._provide.name = func.__name__
        func._provide.flags.update(self.flags)
        for require in self:
            if not require in func._provide:
                func._provide.append(require)
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
        :param require_name: require name
        :type require_name: str

        :rtype: :class:`armonic.require.Require`
        """
        return self.get(require_name)

    def fill(self, variables_values):
        """Fill the provide with variables values.

        :param variables_values: list of tuple (variable_xpath, variable_values)::

            ("//xpath/to/variable", {0: value}),
            ("//xpath/to/variable", {0: value})
        """
        def _filter_values(variables_values):
            # Return only variables for this Provide
            for xpath, values in variables_values:
                provide_name = XMLRegistery.get_ressource(xpath, "provide")
                if not provide_name == self.name:
                    continue
                require_name = XMLRegistery.get_ressource(xpath, "require")
                try:
                    self.require_by_name(require_name)
                except DoesNotExist:
                    continue
                yield (xpath, values)

        for require in self:
            require.fill(_filter_values(variables_values))

    def validate(self):
        """Validate the provide.

        :raises ValidationError: when validation fails
        """
        for require in self:
            logger.debug("Validating %s" % (require))
            try:
                require.validate()
            except ValidationError as e:
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
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "requires": [r.to_primitive() for r in self],
                "flags": self.flags}

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
