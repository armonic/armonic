""" A :class:`Require` permits to a module developper to specify what type of
value it must provide to go to a state. They are specified in
:class:`armonic.lifecycle.State`.

Two subclasses of :class:`Require` can be used if value can be
provided by a lifecycle provider, namely :class:`RequireLocal` and
:class:`RequireExternal`. These requires permit to specify the name of
a provide and what variables it needs and returns. Moreover, it is
sometime intersting to be able to call several time this provide and
then, to use several values returned by this provide (see
:module:`armonic.varnish` for instance).

* :class:`RequireLocal` specify a provide call on the same agent instance.
* :class:`RequireExternal` specify a provide call on an other agent instance.

To provide values to a require, :meth:`Require.fill` method has to
be used. Note that this method is automatically called when a state is
reached. :meth:`Require.fill` take a dict (or a list) of primitive
types to fill values of a require.
"""
import logging
import copy

from armonic.common import IterContainer, DoesNotExist, ValidationError, ExtraInfoMixin
from armonic.variable import Host
from armonic.provide import Provide
from armonic.xml_register import XMLRegistery, XMLRessource


XMLRegistery = XMLRegistery()
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


class Require(XMLRessource, ExtraInfoMixin):
    """Basically, a require is a set of
    :class:`armonic.variable.Variable`. They are defined in a state and
    are used to specify, verify and store values needed to enter in
    this state.

    To submit variable values of a require, :meth:`fill` method
    must be used. Then, method :meth:`validate` can be used to
    validate that values respect constraints defined by the require.

    :param name: name of the require
    :param variables: list of variables
    :param nargs: variables occurences (1 or more, '*', '?')
    """
    def __init__(self, name, variables, nargs='1', **extra):
        ExtraInfoMixin.__init__(self, **extra)
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

        # Variable will be initialized later (in self.variables())
        self._variables = None

    def __call__(self, func):
        """
        Used as a method decorator to define Require on :py:class:`State`
        methods
        Permit to directly use Require constructor as a decorator.
        """
        return Provide(name=None, requires=[self], flags={})(func)

    def _clear(self):
        if self._variables is not None:
            self._init_variables()

    def _init_variables(self):
        # This will contain Variables. fill method will append
        # IterContainer if needed, but we have to initialize it in
        # order to manage default values.
        self._variables = []
        if self.nargs not in ('*', '?') and self._variables_skel:
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

    def factory_variable(self):
        """Return an Itercontainer of variables based on variables_skel

        :rtype: IterContainer of :class:`Variable`
        """
        vars = copy.deepcopy(self._variables_skel)
        return IterContainer(*vars)

    def fill(self, variables_values):
        """
        Fill the require with a list of variables values

        :param variables_values: list of tuple (variable_xpath, variable_values)
            variable_xpath is a full xpath
            variable_values is dict of index=value

        """
        def _filter_values(variables_values):
            # Return only variables for this Require
            for xpath, values in variables_values:
                require_name = XMLRegistery.get_ressource(xpath, "require")
                if not require_name == self.name:
                    continue
                variable_name = XMLRegistery.get_ressource(xpath, "variable")
                try:
                    self.variable_by_name(variable_name)
                except DoesNotExist:
                    continue
                yield (xpath, variable_name, values)

        for xpath, variable_name, values in _filter_values(variables_values):
            for index, value in values.items():
                if not int(index) < self.nargs_max:
                    logger.warning("Ignoring variable value '%s' for %s. Does not conform to nargs definition" % (value, self))
                    continue
                try:
                    variables = self.variables(int(index))
                except DoesNotExist:
                    variables = self.factory_variable()
                    self._variables.append(variables)
                    # TODO: register or not ?
                    # self._xml_register_children()

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
        for (idx, vs) in enumerate(self.variables(all=True)):
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
        primitive = ExtraInfoMixin.to_primitive(self)
        primitive.update({
            "name": self.name,
            "xpath": self.get_xpath_relative(),
            "nargs": self.nargs,
            "nargs_min": self.nargs_min,
            "nargs_max": self.nargs_max,
            "variables": [[var.to_primitive() for var in vars] for vars in self.variables(all=True)],
            "variables_skel": [var.to_primitive() for var in self._variables_skel],
            "type": "simple"}
        )
        return primitive

    def variables(self, index=0, all=False):
        """Return variables of given index.

        TODO: Check if index respect nargs.
        :param index: index of a variable set.
        :param all: if true returns all variables
        :rtype: iterContainer or ([iterContainer] if all == True)
        """
        # If not yet build, variables are built from varaible_skel.
        # This can not be done in __init__ because variable_skel
        # xpaths have to be created.
        if self._variables is None:
            self._init_variables()

        if all:
            return self._variables
        else:
            try:
                return self._variables[index]
            except IndexError:
                raise DoesNotExist("No variables found")

    def variable_by_name(self, variable_name, index=0):
        """From a variable name return the corresponding instance

        :param variable_name: variable name
        :type variable_name: str
        :param index: variable set index
        :type index: int

        :rtype: :class:`Variable`
        """
        try:
            variable = self.variables(index).get(variable_name)
            return variable
        except DoesNotExist:
            # Use variables_skel to resolve xpath even
            # if no variables was set (for validation)
            for variable in self._variables_skel:
                if variable.name == variable_name:
                    return variable
            # No match, raise the exception
            raise

    def get_values(self):
        variables_values = []
        for variable in self._variables_skel:
            variable_values = [variable.get_xpath(), {}]
            for index, variables_set in enumerate(self.variables(all=True)):
                for variable_in_set in variables_set:
                    if variable_in_set.name == variable.name:
                        variable_values[1][index] = variable_in_set.value
                        break
            variables_values.append(variable_values)
        return variables_values

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
    :param nargs: provide occurences (1 or more, '*') or is optional ('?')
    """
    def __init__(self, name, xpath, provide_args=[], provide_ret=[], nargs="1", **extra):
        _variables = provide_args + provide_ret
        Require.__init__(self, name, _variables, nargs=nargs, **extra)
        self.type = "local"
        self.xpath = xpath
        self.provide_args = provide_args
        self.provide_ret = provide_ret

    def _xml_add_properties_tuple(self):
        return ([("xpath", self.xpath)] +
                Require._xml_add_properties_tuple(self))

    def to_primitive(self):
        primitive = Require.to_primitive(self)
        primitive.update({
            "type": self.type,
            "provide_xpath": self.xpath,
            "provide_args": [v.to_primitive() for v in self.provide_args],
            "provide_ret": [v.to_primitive() for v in self.provide_ret]})
        return primitive

    def __repr__(self):
        return "<RequireLocal(name=%s, xpath=%s, provide_args=%s)>" \
            % (self.name, self.xpath, self.provide_args)

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
    def __init__(self, name, xpath, provide_args=[], provide_ret=[], nargs="1", **extra):
        for v in provide_args:
            if v.name == 'host':
                raise RequireDefinitionError(
                    "Variable name 'host' can not be use because it is a"
                    " reserved variable name for External require.")

        RequireLocal.__init__(self, name, xpath,
                              [Host('host', label="Host")] + provide_args,
                              provide_ret, nargs, **extra)
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
        return "<RequireExternal(name=%s, xpath=%s, provide_args=%s)>" \
            % (self.name, self.xpath, self.provide_args)
