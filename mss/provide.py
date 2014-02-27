from mss.common import IterContainer, DoesNotExist, ValidationError
from mss.xml_register import XmlRegister

class Provide(IterContainer, XmlRegister):
    """Basically, this describes a list of :py:class:`Require`."""
    def __init__(self, name, require_list=[], flags=None):
        self.name = name
        IterContainer.__init__(self, *require_list)
        self.flags = flags  # Should not be in Requires ...

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

    def build_args_from_primitive(self, primitive):
        self.build_from_primitive(primitive)
        args = {}
        for a in self.func_args:
            for r in self:
                try:
                    args.update({a: r.variables().get(a).value})
                except DoesNotExist:
                    pass
        return args

    def build_from_primitive(self, primitive):
        """From primitive, fill and validate this requires.

        :param primitive: values for all requires.
        :type primitive: {require1: {variable1: value, variable2: value},
            require2: ...}
        """
        # Fill requires values first
        for require_name, variables_values in primitive.items():
            try:
                require = self.get(require_name)
                logger.debug("Setting %s in %s" % (variables_values, require))
                require.fill(variables_values)
            except DoesNotExist:
                logger.warning("Require %s not found in %s, ignoring" %
                               (require_name, self))
                pass
        # Validate each require
        for require in self:
            logger.debug("Validating %s" % (require))
            try:
                require.validate()
            except ValidationError as e:
                e.require_name = require.name
                raise e

    def has_variable(self, variable_name):
        """Return True if variable_name is specified by this requires."""
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
                "require_list": [r.to_primitive() for r in self],
                "flags": self.flags}

    def __repr__(self):
        return "<Provide:%s(%s,%s)>" % (self.name,
                                         IterContainer.__repr__(self),
                                         self.flags)
