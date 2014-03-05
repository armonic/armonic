""" A :class:`Require` permits to a module developper to specify what type of
value it must provide to go to a state. They are specified in
:py:class:`mss.lifecycle.State`.

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

from mss.common import IterContainer, DoesNotExist, ValidationError
from mss.variable import Host
import copy

from mss.xml_register import XmlRegister

logger = logging.getLogger(__name__)


class RequireNotFilled(Exception):
    """Raise if the value of variable is None."""
    def __init__(self, require_name, variable_name):
        self.variable_name = variable_name
        self.require_name = require_name

    def __repr__(self):
        return "Variable %s in require %s is not filled" % (self.variable_name,
                                                            self.require_name)

    def __str__(self):
        return self.__repr__()


class MissingRequire(Exception):
    def __init__(self, variable="", state=None):
        self.variable = variable
        self.state = state

    def __str__(self):
        return "Require '%s' of state '%s' is missing" % (self.variable,
                                                          self.state)

    def __repr__(self):
        return "Missing require %s" % self.variable


class RequireDefinitionError(Exception):
    """This is raised when the definition of a require is not correct."""
    pass


class Require(XmlRegister):
    """Basically, a require is a set of
    :class:`mss.variable.Variable`. They are defined in a state and
    are used to specify, verify and store values needed to entry in
    this state.

    To submit variable values of a require, :py:meth:`fill` method
    must be used. Then, method :py:meth:`validate` can be used to
    validate that values respect constraints defined by the require.

    :param name: name of the require
    :param variables: list of variables
    :param nargs: variables occurences (1 or more, *, ?)
    """

    def __init__(self, name, variables, nargs='1'):
        self.name = name
        self.type = "simple"

        try:
            if not int(nargs) > 0:
                raise TypeError("nargs must be '1 or more', '?' or '*' (instead of %s)" % nargs)
        except ValueError:
            if not nargs in ["?", "*"]:
                raise TypeError("nargs must be '1 or more', '?' or '*' (instead of %s)" % nargs)
        finally:
            self.nargs = str(nargs)

        if self.nargs == "*":
            self.nargs_min = 0
            self.nargs_max = 99999
        elif self.nargs == "?":
            self.nargs_min = 0
            self.nargs_max = 1
        else:
            self.nargs_min = self.nargs_max = int(self.nargs)

        self._variables_skel = variables
        # This will contain Variables. fill method will append
        # IterContainer if needed, but we have to initialize it in
        # order to manage default values.
        self._variables = []
        if self.nargs not in ('*', '?'):
            for arg in range(self.nargs_max):
                self._variables.append(self.factory_variable())

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        return self._variables_skel

    def _xml_ressource_name(self):
        return "require"

    def _xml_add_properties_tuple(self):
        return [("nargs", self.nargs),
                ("type", self.type)]

    def __call__(self, func):
        """
        Used as a method decorator to define Require on :py:class:`State`
        methods
        Permit to directly use Require constructor as a decorator.
        """
        has_requires = hasattr(func, '_requires')
        require = self
        if has_requires:
            func._requires.append(require)
        else:
            func._requires = [require]
        return func

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
                logger.warning("Variable %s not found in %s, ignoring." %
                               (variable_name, self))
                pass
            except ValidationError:
                raise RequireNotFilled(self.name, variable_name)
        return True

    def factory_variable(self):
        """Return an Itercontainer of variable based on variable
        skeleton.

        :rtype: IterContainer of Variable
        """
        tmp_vars = copy.deepcopy(self._variables_skel)
        return IterContainer(*tmp_vars)

    def fill(self, primitives=[]):
        """Fill variables from a list of primitive.

        NotImplementedYet: We must check if provided primitive
        correspond to nargs.
        """
        if primitives != []:
            # To avoid vaiables append on multiple calls
            self._variables = [IterContainer(*self._variables_skel)]
            self._fill(self._variables[0], primitives[0])
            for primitive in primitives[1:]:
                tmp = self.factory_variable()
                self._fill(tmp, primitive)
                self._variables.append(tmp)
            self._xml_register_children()
        return True

    def new_fill(self, variables_values):
        """
        Fill the require with a list of variables values

        :param variables_values: list of tuple (variable_xpath, variable_values)
            variable_xpath is a full xpath
            variable_values is dict of index=value

        """
        for xpath, values in variables_values:
            variable_name = XmlRegister.get_ressource(xpath, "variable")
            if not self.variable_by_name(variable_name):
                logger.warning("Variable %s not found in %s, ignoring." % (variable_name, self))
                continue

            for index, value in values.items():
                if not int(index) < self.nargs_max:
                    logger.warning("Ignoring variable value '%s' for %s. Does not conform to nargs definition" % (value, self))
                    continue
                try:
                    variables = self._variables[int(index)]
                except IndexError:
                    variables = self.factory_variable()
                    self._variables.append(variables)

                variables.get(variable_name).fill(value)

        return True

    def validate_one_set(self, iterContainer, values={}):
        """Validate Require values on one variables set.
        If values is specified, they are
        used to validate the require variables. Otherwise, you must
        already have fill it because filled values will be used.

        :rtype: boolean"""
        for variable in iterContainer:
            if values:
                try:
                    value = values[variable.name]
                except KeyError:
                    raise ValidationError(
                        variable_name=variable.name,
                        msg="Submitted value doesn't contain key %s" % variable.name)
            else:
                value = variable.value

            variable._validate(variable._validate_type(value))

        return True

    def validate(self, values=[]):
        """Validate Require values. If values is specified, they are
        used to validate the require variables. Otherwise, you must
        already have fill it because filled values will be used.

        :rtype: boolean"""
        for (idx, vs) in enumerate(self._variables):
            if values:
                try:
                    v = values[idx]
                except IndexError:
                    raise ValidationError(
                        "Values must contains as much element"
                        " as variables set elements.")
                self.validate_one_set(vs, v)
            else:
                self.validate_one_set(vs)
        return True

    def to_primitive(self):
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "nargs": self.nargs,
                "nargs_min": self.nargs_min,
                "nargs_max": self.nargs_max,
                "variables": [[var.to_primitive() for var in vars] for vars in self.variables(all=True)],
                "variables_skel": [var.to_primitive() for var in self._variables_skel],
                "type": "simple"}

    def variables(self, index=0, all=False):
        """Return variables of given index.

        TODO: Check if index respect nargs.
        :param index: index of a variable set.
        :param all: if true returns all variables
        :rtype: iterContainer or ([iterContainer] if all == True)
        """
        if all:
            return self._variables
        else:
            return self._variables[index]

    def variable_by_name(self, variable_name):
        """
        :param variable_name: variable name
        :type variable_name: str

        :rtype: :class:`Variable`
        """
        for variable in self._variables_skel:
            if variable.name == variable_name:
                return variable
        return False

    def get_values(self):
        """ FIXME This jsut return the first element"""
        return [reduce(lambda a, x:
                       dict(a.items() + {x.name: x.value}.items()),
                       vs, {}) for vs in self._variables]

    def get_default_values(self):
        """ FIXME This jsut return the first element"""
        return [reduce(lambda a, x:
                       dict(a.items() + {x.name: x.default}.items()),
                       vs, {}) for vs in self._variables]

    def generate_args(self, dct={}):
        """Return a tuple. First element of tuple a dict of
        argName:value where value is the default value. Second is a
        list of argName without default value.

        :param dct: To specify a argName and its value.
        """
        ret = ({}, [])
        for a in self._variables:
            if a.name in dct:
                ret[0].update({a.name: dct[a.name]})
            elif a.has_default_value():
                ret[0].update({a.name: a.default})
            else:
                ret[1].append(a.name)
        return ret

    def __repr__(self):
        return "<Require(name=%s, variables=%s)>" % (self.name,
                                                     self._variables)


class RequireUser(Require):
    """To specify a require which has to be known by user. For
    instance, mysql password is just know by user who must remember
    it."""
    def __init__(self, name, provided_by, variables):
        Require.__init__(self, name, variables)
        self.type = "user"
        self.provided_by = provided_by

    def __repr__(self):
        return "<RequireUser(name=%s, variables=%s)>" % (self.name,
                                                         self._variables)

    def to_primitive(self):
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "variables": [a.to_primitive() for a in self._variables[0]],
                "type": "user",
                "provided_by_xpath": self.provided_by}


class RequireLocal(Require):
    """To specify a configuration variable which can be provided
    by a *provide_name* of a local Lifecycle object.

    nargs parameters permits to specify how many time you can call a
    provide. It can be '1', '?', '*' times. Then, variables is a list
    which will contains many values for each variables.

    :param name: name of the require
    :param xpath: the path of the provide to call
    :param provide_args: default values for the provide
    :param provide_ret: provide return value
    :param nargs: provide occurences (1 or more, *) or is optional (?)
    """
    def __init__(self, name,
                 xpath,
                 provide_args=[],
                 provide_ret=[],
                 nargs="1"):
        _variables = provide_args + provide_ret
        Require.__init__(self, name, _variables, nargs=nargs)
        self.xpath = xpath
        self.lf_name = None
        self.provide_name = None
        self.provide_args = provide_args
        self.provide_ret = provide_ret
        self.name = name
        self.type = "local"
        # This contains Variable submitted
        self._variables_skel = _variables
        # This will contain Variables. fill method will append
        # IterContainer if needed, but we have to initialize it in
        # order to manage default values.
        self._variables = [IterContainer(*_variables)]

    def _xml_add_properties_tuple(self):
        return ([("xpath", self.xpath)] +
                Require._xml_add_properties_tuple(self))

    def to_primitive(self):
        primitive = super(RequireLocal, self).to_primitive()
        primitive.update({
            "type": self.type,
            "lf_name": self.lf_name,
            "provide_xpath": self.xpath,
            "provide_args": [v.to_primitive() for v in self.provide_args],
            "provide_ret": [v.to_primitive() for v in self.provide_ret]})
        return primitive

    def __repr__(self):
        return "<RequireLocal(name=%s, variables=%s, lf_name=%s, provide_name=%s, provide_args=%s)>" \
            % (self.name, self._variables, self.lf_name, self.provide_name, self.provide_args)

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


class RequireExternal(RequireLocal):
    """To specify a configuration variable which can be provided
    by a *provide* of a external module.
    A 'host' variable is automatically added to the args list.
    It MUST be provided.
    """
    def __init__(self, name,
                 xpath,
                 provide_args=[],
                 provide_ret=[],
                 nargs="1"):
        for v in provide_args:
            if v.name == 'host':
                raise RequireDefinitionError(
                    "Variable name 'host' can not be use because it is a"
                    " reserved variable name for External require.")

        RequireLocal.__init__(self, name,
                              xpath,
                              provide_args + [Host('host')],
                              provide_ret, nargs)
        self.type = "external"

    def generate_provide_args(self, dct={}):
        ret = ({}, [])
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
        return "<RequireExternal(name=%s, variables=%s, lf_name=%s, provide_name=%s, provide_args=%s)>" \
            % (self.name, self._variables, self.lf_name, self.provide_name, self.provide_args)
