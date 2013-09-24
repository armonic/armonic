""" This module contains requires classes.

Requires are used to apply a state. The minimal requires definition
MUST contains a method :py:meth:`Require.validate`.

The method :py:meth:`Require.validate` takes as input a list a
dict. Each dict contain a variable name and its value ::

    [{'variable1' : 'value1' , 'variable2' : 'value2' , ...},
     {'variable1' : 'value3' , 'variable2' : 'value4' , ...},
     ...
    ]

"""

import logging

from mss.common import IterContainer, DoesNotExist
from mss.variable import VString


logger = logging.getLogger(__name__)


class MissingRequire(Exception):
    def __init__(self, variable="", state=None):
        self.variable = variable
        self.state = state

    def __str__(self):
        return "Require '%s' of state '%s' is missing" % (self.variable, self.state)

    def __repr__(self):
        return "Missing require %s" % self.variable


class Require(object):
    """Specify configuration variables for a state."""

    def __init__(self, variables, name=None):
        """
        :param args: list of variables
        :param name: name of the require (default: "local")
        """
        self.name = name if name else "this"
        self.variables = IterContainer(variables)
        self.type = "simple"
        self._validated = False

    def fill(self, primitive={}):
        """Fill Require variables

        :param primitive: variables values for this Require
        :type primitive: dict of variable_name: primitive_value
        :rtype: boolean"""
        for variable_name, variable_value in primitive.items():
            try:
                self.variables.get(variable_name).fill(variable_value)
            except DoesNotExist:
                logger.warning("Variable %s not found in %s, ignoring." % (variable_name, self))
                pass
        return True

    def validate(self, values={}):
        """Validate Require values

        :rtype: boolean"""
        for variable in self.variables:
            variable._validate()
        self._validated = True
        return self._validated

    def to_primitive(self):
        return {"name": self.name, "args": [a.to_primitive() for a in self.args],
                "type": "simple"}

    def generate_args(self, dct={}):
        """Return a tuple. First element of tuple a dict of
        argName:value where value is the default value. Second is a
        list of argName without default value.

        :param dct: To specify a argName and its value.
        """
        ret = ({}, [])
        for a in self.variables:
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value:
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret

    def __repr__(self):
        return "<Require(name=%s, variables=%s)>" % (self.name, self.variables)


class RequireLocal(Require):
    """To specify a configuration variable which can be provided
    by a *provide_name* of a local Lifecycle object."""
    def __init__(self, variables, lf_name, provide_name, provide_args=[], name=None):
        Require.__init__(self, variables, name)
        self.lf_name = lf_name
        self.provide_name = provide_name
        self.provide_args = provide_args
        self.name = name if name else "%s.%s" % (self.lf_name, self.provide_name)
        self.type = "local"

    def to_primitive(self):
        return {"name": self.name,
                "type": self.type,
                "lf_name": self.lf_name,
                "provide_name": self.provide_name,
                "provide_args": [v.to_primitive() for v in self.provide_args]}

    def __repr__(self):
        return "<RequireLocal(name=%s, variables=%s, lf_name=%s, provide_name=%s, provide_args=%s)>" % \
                    (self.name, self.variables, self.lf_name, self.provide_name, self.provide_args)

    def generate_provide_args(self, dct={}):
        return self.generate_args(dct)


class RequireVhost(VString):
    pass


class RequireExternal(RequireLocal):
    """To specify a configuration variable which can be provided
    by a *provide* of a external module.
    A 'host' variable is automatically added to the args list.
    It MUST be provided.
    """
    def __init__(self, variables, lf_name, provide_name, provide_args=[], name=None):
        RequireLocal.__init__(self, variables, lf_name, provide_name, provide_args, name)
        self.type = "external"
        self.provide_args.append(RequireVhost('host'))

    def generate_provide_args(self, dct={}):
        ret = ({},[])
        for a in self.provide_args:
            if a.name == 'host':
                continue
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value:
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret

    def __repr__(self):
        return "<RequireExternal(name=%s, variables=%s, lf_name=%s, provide_name=%s, provide_args=%s)>" % \
                    (self.name, self.variables, self.lf_name, self.provide_name, self.provide_args)
