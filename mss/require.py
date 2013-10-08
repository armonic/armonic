""" A :class:`Require` permits to a module developper to specify what type of value
it must provide to go to a state. They are specified in :py:class:`mss.lifecycle.State`.

Two subclasses of :class:`Require` can be used if value can be
provided by a lifecycle provider, namely :class:`RequireLocal` and
:class:`RequireExternal`. These requires permit to specify the name of
a provide and what variables it needs and returns. Moreover, it is
sometime intersting to be able to call several time this provide and
then, to use several values returned by this provide (see
:py:module:`mss.varnish` for instance).

* :class:`RequireLocal` specify a provide call on the same agent instance.
* :class:`RequireExternal` specify a provide call on an other agent instance.

To provide values to a require, :py:meth:`Require.fill` method has to
be used. Note that this method is automatically called when a state is
reached. :py:meth:`Require.fill` take a dict (or a list) of primitive
types to fill values of a require.
"""

import logging

from mss.common import IterContainer, DoesNotExist
from mss.variable import VString
import copy

logger = logging.getLogger(__name__)


class MissingRequire(Exception):
    def __init__(self, variable="", state=None):
        self.variable = variable
        self.state = state

    def __str__(self):
        return "Require '%s' of state '%s' is missing" % (self.variable, self.state)

    def __repr__(self):
        return "Missing require %s" % self.variable


class Requires(IterContainer):
    """Basically, this describes a list of :py:class:`Require`."""
    def __init__(self,name, require_list=[], func_args=[], func_default_args=None, flags=None):
        self.name = name
        IterContainer.__init__(self,require_list)
#        print require_list
#        self._validate_binding_requires_args(func_args)
        self.func_args = func_args
        self.func_default_args = func_default_args
        self._full_name = None
        self.flags = flags # Should not be in Requires ...

    @property
    def full_name(self):
        return self._full_name if self._full_name != None else self.name

    def _set_full_name(self,prefix,separator="."):
        """Build a full name and requires full names by joining
        prefix, separator and name."""
        self._full_name = prefix + separator + self.name

        for r in self:
            r._set_full_name(self._full_name,separator)
        

    def _validate_binding_requires_args(self, args):
        """Validate if all arguments name in args correspond to
        variable name in all requires. If an arguments is not in a
        require, it is added to a generetad Require.
        
        :param requires: Requires object
        :param args: A list of argument name
        """
        variables=[]
        for a in args:
            if not self.has_variable(a):
                logger.debug("Create variable for argument %s" % a)
                variables.append(VString(a))
        if variables != []:
            logger.info("Add generated requires for arguments %s" % variables)
        
        newRequire=Require(variables,"generate_for_missing_args")
        if variables != []:
            self.append(newRequire)


    def build_args_from_primitive(self,primitive):
        self.build_from_primitive(primitive)
        args={}
        for a in self.func_args:
            for r in self:
                try : 
                    args.update({a:r.variables.get(a).value})
                except DoesNotExist:
                    pass
        return args

    def build_from_primitive(self,primitive):
        """From primitive, fill and validate this requires.

        :param primitive: values for all requires.
        :type primitive: {require1: {variable1: value, variable2: value}, require2: ...}
        """
        # Fill requires values first
        for require_name, variables_values in primitive.items():
            try:
                require = self.get(require_name)
                logger.debug("Setting %s in %s" % (variables_values, require))
                require.fill(variables_values)
            except DoesNotExist:
                logger.warning("Require %s not found in %s, ignoring" % (require_name, self))
                pass
        # Validate each require
        for require in self:
            logger.debug("Validating %s" % (require))
            require.validate()


    def has_variable(self, variable_name):
        """Return True if variable_name is specified by this requires."""
        for r in self:
            try : 
                r.variables.get(variable_name)
                return True
            except DoesNotExist:
                pass
        return False

    def get_all_variables(self):
        acc=[]
        for r in self:
            for v in r.variables:
                acc.append(v.name)
        return acc

    def to_primitive(self):
        return {"name": self.full_name, "args": self.func_args, "flags": self.flags}

    def __repr__(self):
        return "<Requires:%s(%s,%s)>" % (self.name, IterContainer.__repr__(self) , self.flags)



class Require(object):
    """Basically, a require is a set of
    :class:`mss.variable.Variable`. They are defined in a state and
    are used to specify, verify and store values needed to entry in
    this state.

    To submit variable values of a require, :py:meth:`fill` method
    must be used. Then, method :py:meth:`validate` can be used to
    validate that values respect constraints defined by the require.

    :param args: list of variables
    :param name: name of the require (default: "local")
    """

    def __init__(self, variables, name=None):
        self.name = name if name else "this"
        self.type = "simple"
        self._validated = False
        self.variables = IterContainer(variables)
        self._full_name = None

    @property
    def full_name(self):
        return self._full_name if self._full_name != None else self.name

    def _set_full_name(self,prefix,separator="."):
        """Build a full name by joining prefix, separator and name."""
        self._full_name = prefix + separator + self.name
        for v in self.variables:
            v._set_full_name(self._full_name,separator)

    @staticmethod
    def specify(require):
        """This is a decorator to specify a method that can be used as a provide in a state.
        Requires are checked in order to know if all function arguments are specified by it.

        Be careful, without flags, this decorator should be used as
        following @provide()
        """
        def wrapper(func):
            if hasattr(func,'_requires'):
                func._requires.append(require)
            else: func._requires=[require]
            return func
        return wrapper


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
        """Fill variable values from a dict.

        :param primitive: variables values for this require
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
            elif a.has_default_value():
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret

    def __repr__(self):
        return "<Require(name=%s, variables=%s)>" % (self.name, self.variables)


class RequireUser(Require):
    """To specify a require which has to be known by user. For
    instance, mysql password is just know by user who must remember
    it."""
    def __init__(self, name, provided_by, variables):
        Require.__init__(self,variables,name)
        self.type = "user"
        self.provided_by = provided_by
    def __repr__(self):
        return "<RequireUser(name=%s, variables=%s)>" % (self.name, self.variables)



class RequireLocal(Require):
    """To specify a configuration variable which can be provided
    by a *provide_name* of a local Lifecycle object.

    nargs parameters permits to specify how many time you can call a
    provide. It can be '1', '?', '*' times. Then, variables is a list
    which will contains many values for each variables.

    :param nargs: occurence number of variables.
    :type nargs: ["1","?","*"].
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

    def _set_full_name(self,prefix,separator="."):
        """Build a full name by joining prefix, separator and name."""
        self._full_name = prefix + separator + self.name
        for i in self.variables:
            for v in i:
                v._set_full_name(self._full_name,separator)

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
            # To avoid vaiables append on multiple calls
            self.variables = [IterContainer(self._variables_skel)]
            self._fill(self.variables[0],primitives[0])
            for primitive in primitives[1:]:
                tmp=IterContainer(copy.deepcopy(self._variables_skel))
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

    def generate_args(self, dct={}):
        """Return a tuple. First element of tuple a dict of
        argName:value where value is the default value. Second is a
        list of argName without default value.

        :param dct: To specify a argName and its value.
        """
        ret = ({}, [])
        for a in self._variables_skel:
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value():
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret

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
        RequireLocal.__init__(self, lf_name, provide_name, provide_args + [VString('host')], provide_ret, name, nargs)
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
