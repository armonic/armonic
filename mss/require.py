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
    """Specify configuration variables for a state.
    """

    def __init__(self, variables, name=None):
        """
        :param args: list of variables
        :param name: name of the require (default: "local")
        :param nargs: occurence number of variables.
        :type nargs: ["1","?","*"].
        """
        self.name = name if name else "this"
        self.type = "simple"
        self._validated = False
        self.variables = IterContainer(variables)

    def _fill(self, iterContainer, primitive):
        """Fill an iterContainer with value found in primitive.
        :param iterContainer: contains some variables.
        :type iterContainer: iterContainer.
        :type primitive: dict of variable_name: primitive_value.
        :rtype: boolean."""
        for variable_name, variable_value in primitive.items():
            try:
                iterContainer.get(variable_name).fill(variable_value)
            except DoesNotExist:
                logger.warning("Variable %s not found in %s, ignoring." % (variable_name, self))
                pass
        return True
        

    def fill(self, primitive={}):
        """Fill Require variables

        :param primitive: variables values for this Require
        :type primitive: dict of variable_name: primitive_value
        :rtype: boolean"""
        return self._fill(self.variables,primitive)


    def _validate(self, iterContainer, values={}):
        """Validate Require values

        :rtype: boolean"""
        for variable in iterContainer:
            variable._validate()
        self._validated = True
        return self._validated

    def validate(self, values={}):
        """Validate Require values

        :rtype: boolean"""
        return self._validate(self.variables,values)

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
    by a *provide_name* of a local Lifecycle object.

    nargs parameters permits to specify how many time you can call a
    provide. It can be '1', '?', '*' times. Then, variables is a list
    which will contains many values for each variables.
    """
    def __init__(self, lf_name, provide_name, provide_args=[], provide_ret=[], name=None, nargs="1"):
        variables=provide_args + provide_ret
        Require.__init__(self, variables, name)
        self.lf_name = lf_name
        self.provide_name = provide_name
        self.provide_args = provide_args
        self.provide_ret = provide_ret
        self.name = name if name else "%s.%s" % (self.lf_name, self.provide_name)
        self.type = "local"
        if nargs not in ["1","?","*"]:
            raise TypeError("nargs must be '1', '?' or '*' (instead of %s)"%nargs)
        self.nargs = nargs
        # This contains Variable submitted
        self._variables_skel = variables
        # This will contain Variables. fill method will append
        # IterContainer if needed, but we have to initialize it in
        # order to manage default values.
        self.variables = [IterContainer(variables)]

    
    def fill(self,primitives=[]):
        """Fill variables from a list of primitive. If primitive is
        not a list, then it is encapsulated in a list. This permit to
        easily managed request from cli. Need to be FIXED.

        NotImplementedYet: We must check if provided primitive
        correspond to nargs.
        """
        if type(primitives) is not list:
            primitives=[primitives]
        if primitives != []:
            self._fill(self.variables[0],primitives[0])
            for primitive in primitives[1:]:
                tmp=IterContainer(self._variables_skel)
                self._fill(tmp,primitive)
                self.variables.append(tmp)
        return True

    def validate(self, values={}):
        """Validate Require values

        :rtype: boolean"""
        for v in self.variables:
            self._validate(v,values)
        return True


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
    def __init__(self, lf_name, provide_name, provide_args=[], provide_ret=[], name=None, nargs="1"):
        RequireLocal.__init__(self, lf_name, provide_name, provide_args + [RequireVhost('host')], provide_ret, name, nargs)
        self.type = "external"

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
