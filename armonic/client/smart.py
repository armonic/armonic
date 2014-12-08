"""Smart module offers a high level way to call a provide. Function
:func:`smart_call` generates steps to help the user to

* define LifecycleManager,
* specialize xpath provide,
* specify variable value,
* ...

To use this module, you have to create a
:py:class:`armonic.client.smart.Provide`, and call
:py:func:`armonic.client.smart.smart_call`. In the following, the
classical code to use this library.

First, we define by inheritance global behavior of provides. In this
example, we want to 'manage' all provides::

    from armonic.client.smart import Provide, smart_call

    class MyProvide(Provide):
        def on_manage(self, data):
            return True


Then, we can build a provide from this classe and call smart_call on
it which returns a generator. We use this generator to walk on provides::

    my_provide = MyProvide("//a/xpath)
    generator = smart_call(my_provide)
    data = None
    while True:
        provide, step, args = generator.send(data)
        data = None

        if step == "manage":
            print "Provide %s is managed!" % provide.generic_xpath
        elif step == "specialize":
            # Do others stuffs on specialize step
            # ...
        elif step == ....


Some tips about how it works...
-------------------------------

About provide_ret validation:
Since provide_ret variables's values are known at runtime, we need to
do special thing to pass agent validation before deployement. Smart
ignore validation errors returned by agents if error occurs on
variables that belongs to provide_ret.
"""

# Limitiations
#
# It's not able to manage several require (nargs) variable.
# It's not able to manage path

import logging
import json

from armonic.client.utils import require_validation_error
import armonic.common

logger = logging.getLogger(__name__)

# The name of the special require name created the xapth that
# represents provide_ret value.
SPECIAL_REQUIRE_RETURN_NAME = "return"

# Describe the step that sent (through the generator) values used for
# the deployment
STEP_DEPLOYMENT_VALUES = "deployment_values"

STEPS = ["manage",
         "lfm",
         "specialize",
         "multiplicity",
         "validation",
         "call",
         "done"]


def generate_pre_post_steps(step):
    return ["pre_" + step, step, "post_" + step]
STEPS = reduce(lambda acc, steps: acc + steps,
               map(generate_pre_post_steps, STEPS),
               [])


class ValidationError(Exception):
    pass


class SmartException(Exception):

    @property
    def name(self):
        return self.__class__.__name__


class PathNotFound(SmartException):
    pass


class Variable(object):
    """
    :param from_require: The require that holds this variable.
    :param belongs_provide_ret: True if this variable belongs to the provide_ret variable list of the from_require.
    """

    def __init__(self, name, from_require, xpath, from_xpath, default, value, required, type, error, belongs_provide_ret, modifier, extra):
        self.from_require = from_require
        self.name = name
        self.xpath = xpath
        self.from_xpath = from_xpath
        self._default = default
        self._value = value
        self.required = required
        self.type = type
        self.error = error
        self.extra = extra
        self.modifier = modifier
        self._is_skel = True

        self.belongs_provide_ret = belongs_provide_ret

        # Capture the xpath that provides the value for this
        # variable. The format of this XPath is
        # <location>/<lifecycle>/<state>/<provide>/return/variable_name
        #
        # If its value is None, that means the provide is not managed
        # by smart and the value has to be manually provided.
        #
        # You should use the property provided_by_xpath in order to auto
        # update this field.
        self._provided_by_xpath = None

        # Capture the variable used to resolve self
        self._resolved_by = None
        self._set_by = None
        self._suggested_by = None

        # Used as a guard to break cycles during variable resolution
        self._resolving = False

        # Used for debugging.
        self._has_value = False

        logger.debug("Created variable @%s %s" % (id(self), self.xpath))

    def copy(self, from_require):
        var = Variable(
            name=self.name,
            from_require=from_require,
            xpath=self.xpath,
            from_xpath=self.from_xpath,
            default=self._default,
            value=self._value,
            required=self.required,
            type=self.type,
            error=self.error,
            belongs_provide_ret=self.belongs_provide_ret,
            modifier=self.modifier,
            extra=self.extra)

        var._is_skel = False

        # All variable are added to a global list
        self.from_require.from_provide.Variables.append(var)

        return var

    @classmethod
    def from_json(cls, dct_json, from_require, belongs_provide_ret=False):
        """
        :param dct_json: a dict that contains values from agent
        :param from_require: the require that declares this variables
        :param belongs_provide_ret: True if this variable belongs to the provide_ret variable list of the from_require
        """
        this = cls(dct_json['name'],
                   from_require=from_require,
                   xpath=dct_json['xpath'],
                   from_xpath=dct_json['from_xpath'],
                   default=dct_json['default'],
                   value=None,
                   required=dct_json['required'],
                   type=dct_json['type'],
                   error=dct_json['error'],
                   belongs_provide_ret=belongs_provide_ret,
                   modifier=dct_json['modifier'],
                   extra=dct_json['extra'])
        return this

    def update_from_json(self, dct_json):
        for key, value in dct_json.items():
            # We don't update the value from the json generated by
            # agent. Indeed, the agent doen't have to change this
            # value. In fact, we don't do this because the json
            # variable specification is not sufficient to manage
            # multiplicity of variables. See commit message also.
            if key not in "value":
                try:
                    setattr(self, key, value)
                except AttributeError:
                    logger.error("Error: Failed to update attr %s to %s" % (key, value))

    @property
    def provided_by_xpath(self):
        """If this variable belongs to a provide_ret, return None if the
        Provide that has to provide the value is not managed by
        smart. In this case, user will have to fill it manually.
        """
        if (self.belongs_provide_ret and
                self.from_require.provide is not None and
                self.from_require.provide.manage):
            return "/".join([
                self.from_require.provide._node_id.to_str(),
                self.from_require.provide.xpath,
                SPECIAL_REQUIRE_RETURN_NAME,
                self.name])
        else:
            return None

    @property
    def default(self):
        return self._default

    @default.setter
    def default(self, default):
        self._default = default

    @property
    def default_resolved(self):
        """Returns the value resolved."""
        return self._resolved_break_cycles(
            lambda a: a._default,
            lambda a: a.default_resolved)

    def _apply_modifier(self, value):
        """If self.modifier is not None, we currently apply it only on
        VString."""
        if value is not None and self.modifier is not None:
            if self.type == 'str':
                return self.modifier % value
        return value

    @property
    def value(self):
        v = self.value_resolved
        if self._has_value is False and v is not None:
            self._has_value = True
            logger.debug("Variable (@%s) %s gets the value %s" % ((id(self)), self.xpath, v))
        return self._apply_modifier(v)

    @value.setter
    def value(self, value):
        self._value = value

    def value_get_one(self):
        """Try to get a value from default, or resolved."""
        return (self.value_resolved or
                self.value or
                self.default_resolved or
                self.default)

    @property
    def value_resolved(self):
        """Returns the value resolved."""
        return self._apply_modifier(
            self._resolved_break_cycles(
                lambda a: a._value,
                lambda a: a.value_resolved))

    def _resolved_break_cycles(self, f_value, f_resolved):
        """Returns the value resolved and breaks potential cycles.
        :param f_value: is a function returing the local value.
        :param f_resolved: is a function returing the value resolved by other variables.
        """
        if self._resolving:
            # If this variable resolution is started, we stop the
            # recursion here without returning any value.
            # The self value can be use at the first iteration.
            return None
        else:
            self._resolving = True
            self._bind()
            resolved = self._resolve()
            if resolved is self:
                value = f_value(self)
            else:
                value = f_resolved(resolved)
                # If the resolved value is None, we try the self value
                # which may be not None!
                if value is None:
                    value = f_value(self)

            self._resolving = False
            return value

    def _resolve(self):
        """When bindings have been created, this method can be used to get a
        bound variable. First, we try to get the variable set_by, then
        suggested_by, then resolved_by and finally, we use self."""
        if self._set_by is not None:
            return self._set_by
        elif self._suggested_by is not None:
            return self._suggested_by
        elif self._resolved_by is not None:
            return self._resolved_by
        else:
            return self

    def _bind(self):
        """Try to bind this variable to another one by assigning attributes
        _resolved_by, _set_by or _suggested_by.

        If from_xpath is not None, it tries to to find back the
        corresponding variable. Otherwise, it tries to find a value in
        the scope.

        'host' variables are particular cases.
        """
        scope = self.from_require._scope_variables

        if self.type == 'armonic_this_host' and self.from_require.from_provide is not None:
            self._value = self.from_require.from_provide.host
            return

        # Variables type armonic_hosts is a special kind of variable. To
        # fill it, we accumulate host value of all brothers of this provide.
        if self.type == 'armonic_hosts' and self.from_require.from_provide.require:
            self._value = [r.provide.host for r in self.from_require.from_provide.require._from_requires]

        if self.type == 'armonic_host' and self._value is None:
            if self.from_require.type == 'external' and self.from_require.provide:
                self._value = self.from_require.provide.host
                # FIXME: We have a problem because host doesn't come from a variable!
                return
            # Auto-fill the value if ArmonicHost specified in a Require
            if self.from_require.type == 'simple' and self.from_require.from_provide:
                self._value = self.from_require.from_provide.host
                return

        # armonic_host variables must not be resolved.
        if self.type == 'armonic_host':
            return

        # If the variable has a from_xpath attribute,
        # try to find back its value
        if self.from_xpath is not None:
            for v in self.from_require.from_provide.Variables:
                if v.xpath == self.from_xpath:
                    self._set_by = v
                    logger.debug("Variable [%s] value comes from [%s] (@%s) with value %s" % (
                        self.xpath, v.xpath, id(v), v._value))
                    return
            logger.info("Variable [%s] from_xpath [%s] not found" % (
                self.xpath, self.from_xpath))

        if self.from_require.special and not self.name == 'host':
            return

        if self.from_xpath is None:
            for v in scope:
                if self.name == v.name and self is not v:
                    logger.trace("Variable [%s] is suggested by [%s] with value %s" % (
                        self.xpath, v.xpath, v._value))
                    logger.trace("Variable [%s] is resolved by [%s] with value %s" % (
                        v.xpath, self.xpath, v._value))
                    self._suggested_by = v
                    v._resolved_by = self

    def pprint(self):
        return {"name": self.name,
                "xpath": self.xpath,
                "default": self._default,
                "value": self.value,
                "error": self.error}

    def __repr__(self):
        return "Variable(skel=%s, %s, name=%s, xpath=%s, value=%s, error=%s)" % (
            self._is_skel,
            id(self),
            self.name,
            self.xpath,
            self._value,
            self.error)


class Requires(list):
    """This class is used to represent the require multiplicity."""
    def __init__(self, skel):
        self.skel = skel

    def get_new_require(self):
        new = self.skel.copy()
        new._from_requires = self
        try:
            new.child_num = self[-1].child_num + 1
        except IndexError:
            pass
        new.multiplicity_num = len(self)
        self.append(new)
        return new

    def variables_serialized(self):
        dct = {}
        for (i, r) in enumerate(self):
            for v in r.variables():
                if v.xpath not in dct:
                    dct[v.xpath] = {i: v.value}
                else:
                    dct[v.xpath].update({i: v.value})

        acc = []
        for (k, v) in dct.items():
            acc.append((k, v))
        return acc

    def variables(self):
        acc = []
        for r in self:
            acc += r.variables()
        return acc


class Require(object):
    """
    :param from_provide: The provide that holds this require.

    """

    def __init__(self, from_provide, special, child_num):
        self._is_skel = True

        self.child_num = child_num

        # Since the same require can be requried several times (via
        # multiplicity), this attribute describes the index of this
        # require amongst all same require.
        self.multiplicity_num = 0

        self.from_provide = from_provide
        self._from_requires = None
        # If this require comes from a special provide, ie. entry,
        # leave or cross. This is used to avoir variable value
        # propagation to require that comes from states.
        self.special = special
        self._scope_variables = []

        # We copy variables dict from parent the scope.
        # They will be upgraded when requires are built.
        if from_provide.require is not None:
            for v in from_provide.require._scope_variables:
                self._scope_variables.append(v)

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        this = cls(**kwargs)
        this.xpath = dct_json['xpath']
        this.type = dct_json['type']
        this.name = dct_json['name']

        this._variables = []
        for v in dct_json['variables_skel']:
            this._variables.append(Variable.from_json(v, from_require=this))

        this.json = dct_json
        return this

    def copy(self):
        new = Require(from_provide=self.from_provide,
                      special=self.special,
                      child_num=self.child_num)
        # To know if this instance is a skeleton or not.
        new._is_skel = False

        new.xpath = self.xpath
        new.type = self.type
        new.name = self.name

        new._variables = []
        for v in self._variables:
            new._variables.append(v.copy(new))

        new.json = self.json
        return new

    def pprint(self):
        return {"xpath": self.xpath,
                "variables": [v.pprint() for v in self._variables]}

    def variables_serialized(self):
        """Get variables in the format for provide_call"""
        acc = []
        for v in self._variables:
            acc.append((v.xpath, {0: v.value}))
        return acc

    def variables(self):
        """:rtype: [:class:`Variable`]"""
        return self._variables


class Remote(Require):
    def __init__(self, from_provide, special, child_num):
        Require.__init__(self, from_provide, special, child_num)
        self.provide = None

    def copy(self):
        new = Remote(from_provide=self.from_provide,
                     special=self.special,
                     child_num=self.child_num)
        # To know if this instance is a skeleton or not.
        new._is_skel = False

        new.xpath = self.xpath
        new.type = self.type
        new.name = self.name
        new.nargs = self.nargs
        new.provide_xpath = self.provide_xpath

        new.provide_args = []
        for v in self.provide_args:
            new_variable = v.copy(new)
            new.provide_args.append(new_variable)
            new._scope_variables.append(new_variable)

        new.provide_ret = []
        for v in self.provide_ret:
            new_variable = v.copy(new)
            new.provide_ret.append(new_variable)
            new._scope_variables.append(new_variable)

        new.json = self.json
        return new

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        this = cls(**kwargs)
        this.xpath = dct_json['xpath']
        this.type = dct_json['type']
        this.name = dct_json['name']

        this.nargs = dct_json['nargs']
        this.provide_xpath = dct_json['provide_xpath']
        this.provide_args = []

        for v in dct_json['provide_args']:
            var = Variable.from_json(v, from_require=this)
            this.provide_args.append(var)

            # This variable is added to the scope.
            # This should useless since it is the skeleton
            # this._scope_variables.append(var)

        # Here, we add provide ret variable.
        this.provide_ret = []
        for v in dct_json['provide_ret']:
            var = Variable.from_json(v, from_require=this,
                                     belongs_provide_ret=True)
            this.provide_ret.append(var)

            # This variable is added to the scope.
            # this._scope_variables.append(var)

        this.json = dct_json
        return this

    def pprint(self):
        return {"xpath": self.xpath,
                "variables": [v.pprint() for v in self.provide_args]}

    def variables_serialized(self):
        """Get variables in the format for provide_call"""
        acc = []
        for v in (self.provide_args + self.provide_ret):
            acc.append((v.xpath, {0: v.value}))
        return acc

    def variables(self):
        """:rtype: [:class:`Variable`]"""
        acc = [v for v in self.provide_args]
        for v in self.provide_ret:
            acc.append(v)
            if v.provided_by_xpath is None:
                pass
            else:
                logger.debug("Variable %s will be provided_by_xpath by %s" % (
                    v.xpath, v.provided_by_xpath))
        return acc

    def update_provide_ret(self, provide_ret):
        for (name, value) in provide_ret.items():
            for v in self.provide_ret:
                if v.name == name:
                    v._value = value
                    logger.debug("Variable %s has been updated with value "
                                 "'%s' from provide_ret" % (v.xpath, value))
                    break


class ArmonicProvide(object):

    def __init__(self):
        self.xpath = None
        self.name = ""
        self.extra = {}

    def _build_provide(self, provide_xpath_uri):
        provides = self.lfm.provide(provide_xpath_uri)
        # FIXME: This should not happen.  But this happens if a
        # provide from a replay file is used and the module is not
        # loaded for instance.
        if len(provides) < 1:
            msg = "The XPath used to build the provide doesn't match anything."
            logger.error(msg)
            raise Exception(msg)
        self.update_from_json(provides[0])

    def update_from_json(self, dct_json):
        self.name = dct_json['name']
        self.xpath = dct_json['xpath']
        self.extra = dct_json.get('extra', {})

    def ignore_error_on_variable(self, variable):
        """Can be overlapped to ignore validation error on some variables."""
        return False


class NodeId(object):
    def __init__(self, node_id):
        self._node_id = node_id

        # Old node id can come from a deployment info file
        self._old_node_id = None

    def __repr__(self):
        return "node_" + "_".join([str(n) for n in self._node_id])

    def to_str(self):
        return "node_" + "_".join([str(n) for n in self._node_id])

    def old_is_set(self):
        return self._old_node_id is not None

    def old_to_str(self):
        return str(self._old_node_id)


class Provide(ArmonicProvide):
    """This class describe a provide and its requires and remotes requires
    contains provide. Thus, this object can describe a tree. To build
    the tree, the function :func:`smart_call` must be used.

    To adapt the behavior of this class, redefine methods on_step and
    do_step, where step is manage, lfm, specialize, etc.
    If method do_step returns True, this step is 'yielded'.
    Method on_step takes as input the sent data.

    :param child_number: if this Provide is a dependencies, this is
                         the number of this child.
    :param requirer: the provide that need this require
    :param require: the remote require of the requirer that leads
                    to this provide.
    """
    # Contains all variables. This is used to find back from_xpath value.
    Variables = []

    require = None
    """Contains the :class:`Require` that requires this provide."""

    requirer = None
    """Contains the :class:`Provide` that requires this current
    provide."""

    def __init__(self, generic_xpath, requirer=None,
                 child_num=None, require=None):
        ArmonicProvide.__init__(self)

        self.generic_xpath = generic_xpath

        # the provide that need this require
        self.requirer = requirer

        # the remote require of the requirer that leads
        # to this provide.
        self.require = require

        # This dict contains variables that belongs to this scope.
        self._scope_variables = {}

        # If this provide is the Root provide
        # We initialize depth and tree_id
        #
        # NOTE: depth could be deduce from tree_id: depth = len(tree_id)
        if not self.has_requirer():
            self.depth = 0
            self.tree_id = [0]
        else:
            self.depth = requirer.depth + 1
            self.tree_id = requirer.tree_id + [child_num]

        # This will replace tree_id.
        self._node_id = NodeId(self.tree_id)

        # self.ignore = False
        self._step_current = 0

        self._current_requires = None
        self._children_generator = None

        # Contain all requires. A require can be several time in this
        # list due to multiplicity.
        self._requires = None

        # Provide configuration variables.
        #
        # If this provide comes from a local require, the lfm is taken
        # from the requirer.
        self.lfm = None

        # the host contains the adress (IP or DNS) used to contact the
        # service.
        self._host = None

        # lfm_host contain the adress used to contact this agent
        self.lfm_host = None

        self.is_local = False
        if (require is not None and
                require.type == "local"):
            self.lfm = requirer.lfm
            self.host = requirer.host
            self.lfm_host = requirer.lfm_host
            self.is_local = True

        self.is_external = False
        if (require is not None and
                require.type == "external"):
            self.is_external = True
        # consider the root_provide like an external require
        if requirer is None:
            self.is_external = True

        self.manage = True
        self.call = None

        # True when all variables are validated
        self.is_validated = False

    def __repr__(self):
        return "<Provide(%s)>" % self.generic_xpath

    @property
    def host(self):
        # When filling ArmonicHosts we need the host
        # value of each Provide but each Provide might
        # not have any lfm setup yet.
        #
        # FIXME: We should introduce attribute lfm_data which is would
        # contain the data created at step lfm and used by on_lfm
        # method. Currently, we are supposing in smart that lfm_host
        # is created at step lfm. However, smart should not do this
        # kind of assumptions.
        #
        if self._host is None and self.lfm_host:
            self.on_lfm(self.lfm_host)
        return self._host

    @host.setter
    def host(self, value):
        self._host = value

    def variables_serialized(self):
        """Get variables in the format for provide_call"""
        acc = []
        for r in self.remotes + self.requires:
            acc += r.variables_serialized()
        return (acc, {'source': None, 'uuid': None})

    def variables(self):
        """:rtype: [:class:`Variable`]"""
        acc = []
        for v in self.remotes + self.requires:
            acc += v.variables()
        return acc

    def variables_scope(self):
        """Return the variable scope of this provide.

        :rtype: [:class:`Variable`]

        """
        if self.require is not None:
            return self.require._scope_variables
        return []

    def validate(self, values, static=False):
        """Validate all variables using values from data. Moreover, variable
        value is set with values coming from data.

        The static validation is used to validate variables before
        deployment is running. In this case, we don't handle error on
        provide_ret's variables since we don't know value returned by
        porvide calls.

        :param static: If True, run a static validation.
        :rtype: bool
        """
        # Update scope variables with values
        for variable in self.variables():
            idx = variable.from_require.multiplicity_num
            for variable_xpath, variable_values in values:
                if variable.xpath == variable_xpath:
                    # FIXME - can have multiple values
                    try:
                        variable.value = variable_values[idx]
                    except KeyError:
                        # FIXME web interface send string indexes
                        try:
                            variable.value = variable_values[str(idx)]
                        except KeyError:
                            variable.value = None
                    logger.debug("Updating from user specified value %s=%s" % (variable_xpath, variable.value))

        values = (values, {'source': None, 'uuid': None})
        result = self.lfm.provide_call_validate(self.xpath,
                                                self.variables_serialized())
        errors = False

        json_variables = []
        for require in result['requires']:
            for r in require['requires']:
                # FIXME: handle nargs
                if len(r['variables']) > 0:
                    for v in r['variables'][0]:
                        json_variables.append(v)

        for variable in self.variables():
            for json_variable in json_variables:
                if variable.xpath == json_variable['xpath']:
                    # If a static validation is asked, we don't
                    # consider the error if the variable belongs to
                    # the provide_ret of the require.
                    if json_variable['error'] is not None:
                        if (variable.belongs_provide_ret and static):
                            pass
                        elif self.ignore_error_on_variable(variable):
                            logger.info("Ignoring error of variable %s (due to provide.ignore_error_on_variable())" % variable.xpath)
                        else:
                            errors = True
                    variable.update_from_json(json_variable)
                    if variable.error:
                        if armonic.common.SIMULATION:
                            logger.debug("Variable %s has error: %s" % (variable.xpath, variable.error))
                        else:
                            logger.error("Variable %s has error: %s" % (variable.xpath, variable.error))

        self.is_validated = not errors

        return self.is_validated

    def has_requirer(self):
        """To know if it is the root provide."""
        return self.requirer is not None

    @property
    def step(self):
        return STEPS[self._step_current]

    def _next_step(self):
        if self._step_current + 1 > len(STEPS) - 1:
            raise IndexError
        self._step_current += 1

    def _previous_step(self):
        try:
            if STEPS[self._step_current - 1]:
                self._step_current -= 1
        except IndexError:
            pass

    def _build_require_from_call_require(self, dct_json):
        """From a json dict, build Require and Remote require."""
        self.remotes = []
        self.requires = []
        idx = 0

        # Here, a not really clean hack to order requires.
        # We begin with 'remote' requires because to give to them
        # first child indexes.
        for p in dct_json:
            special = p['name'] in ['enter', 'leave', 'cross']
            for require in p['requires']:
                if require['type'] in ['external', 'local']:
                    self.remotes.append(Requires(Remote.from_json(
                        require, special=special, child_num=idx, from_provide=self)))
                    idx += 1
        # Then, we give last indexes to simple requires.
        for p in dct_json:
            special = p['name'] in ['enter', 'leave', 'cross']
            for require in p['requires']:
                if require['type'] in ['simple']:
                    requires = Requires(Require.from_json(
                        require, special=special, child_num=idx, from_provide=self))
                    requires.get_new_require()
                    self.requires.append(requires)
                    idx += 1

    def _build_requires(self):
        """Get all requires"""
        provides = self.lfm.provide_call_requires(self.xpath)
        self._build_require_from_call_require(provides)

    def _requirator(self):
        """Be careful, this function always returns the same generator."""
        def c():
            for r in self.remotes:
                yield r

        if self._children_generator is None:
            self._children_generator = c()

        return self._children_generator

    def build_child(self, generic_xpath, child_num, require):
        """Build and return a new provide by using the same class. """
        ret = self.__class__(generic_xpath,
                             requirer=self,
                             child_num=child_num,
                             require=require)
        return ret

    def do_lfm(self):
        """The step lfm is applied if it returns True.

        Currently, do_lfm is already called, even if the provide is
        local. We may only call it when the provide is external

        """
        # If lfm_host is set at the multiplicity step
        # we can create the lfm automatically
        if self.lfm_host:
            self.on_lfm(self.lfm_host)
        return self.lfm is None

    def on_lfm(self, lfm):
        self.lfm = lfm

    def _test_lfm(self):
        """Verify that lfm and lfm_host attributes are set."""
        if self.lfm is None:
            raise AttributeError("'lfm' attribute must not be None. Must be set at 'lfm' step")
        if self.lfm_host is None:
            raise AttributeError("'lfm_host' attribute must not be None. Must be set at 'lfm' step")

    def reset_lfm(self):
        """
        Reset all data set at the lfm step
        """
        self.lfm = self.lfm_host = self.host = None

    def do_call(self):
        return self.call is None

    def on_call(self, call):
        """
        :type call: boolean
        """
        self.call = call

    def _test_call(self):
        """
        :type call: boolean
        """
        if self.call is None:
            raise AttributeError("'call' attribute must not be None. Must be set at 'call' step")

    def do_multiplicity(self):
        return True

    def on_multiplicity(self, requires, data):
        """Can be overload to adapt behavior of multiplicity step.
        This method must return either a number or a list.

        This is different than others steps because we can not bind
        the multiplicity value to the provide object since each
        require have its own multiplicity.

        Moreover, on_multiplicity is always called even if
        do_multiplicity returns False.

        :type requires: Requires
        """
        return data

    def do_manage(self):
        return True

    def on_manage(self, data):
        self.manage = data

    def _test_manage(self):
        if self.manage is None:
            raise AttributeError("'manage' attribute must not be None. Must be set at 'manage' step")

    def matches(self):
        """Return the list of provides that matched the generic_xpath"""
        return self.lfm.provide(self.generic_xpath)

    def on_specialize(self, xpath):
        """Actions after the provide has been specialized."""
        pass

    def do_specialize(self):
        """Specialization can not be avoided. If the provide matches only 1
        xpath, yield doesn't occurs if this method returns False.

        Thus, by returning True, specialization always yields.
        """
        return False

    def do_validation(self):
        return True

    def update_scope_provide_ret(self, provide_ret):
        """When the provide call returns value, we habve to update the scope
        of the require in order to be able to use these value to fill
        depending provides.
        """
        # A provide should ALWAYS return a dict.
        if type(self.provide_ret) is dict:  # FIXME
            if self.has_requirer():
                self.require.update_provide_ret(self.provide_ret)

    def lfm_call(self):
        if not armonic.common.DONT_VALIDATE_ON_CALL:
            # FIXME. This is a temporary hack!
            ret = self.lfm.provide_call_validate(
                provide_xpath_uri=self.xpath,
                requires=self.variables_serialized())
            if ret['errors']:
                logger.error("Following variables have not been validated:")
                for v in require_validation_error(ret):
                    logger.error("\t%s" % str(v))
                ValidationError("Some variables have not been validated before provide_call!")

        self.provide_ret = self.lfm.provide_call(
            provide_xpath_uri=self.xpath,
            requires=self.variables_serialized())
        if type(self.provide_ret) is not dict:
            logger.debug("Provide '%s' return type is %s (instead a dict)!" % (self.xpath, type(self.provide_ret)))
        else:
            logger.info("Provide '%s' returns:" % self.xpath)
            for k, v in self.provide_ret.items():
                logger.info("- %s : %s" % (k, json.dumps(v)))

        self.update_scope_provide_ret(self.provide_ret)
        # self.provide_ret = self.lfm.call("provide_call_validate",
        #                                  provide_xpath_uri=self.xpath,
        #                                  requires=self.variables_serialized())
        # from pprint import pprint
        # pprint(self.provide_ret)

        return self.provide_ret


class XpathNotFound(Exception):
    pass


class Deployment(object):
    """ To create a replay file.

    The 'mapping' section store relationship between old and new node id.
    """

    def __init__(self, scope, sections):
        # Variable are splitted into input and output because we don't try
        # to update input file to generate the output one. We regenerate
        # the output file each time smart is called.
        # This simplifies the process of node_id mapping if node_id have changed.
        self._manage_input = []
        self._lfm_input = []
        self._specialize_input = []
        self._multiplicity_input = []
        self._variables_input = []

        self._manage_output = []
        self._lfm_output = []
        self._specialize_output = []
        self._multiplicity_output = []
        self._variables_output = []
        # Contains variable that belongs to provide_ret require part
        self._variables_output_provide_ret = []
        # Contains variable which type is armonic_host or armonic_hosts.
        # They can need special translation at deployement time.
        self._variables_output_host = []
        self._mapping_output = []

        for section_name, section in sections.items():
            try:
                for key, value in section:
                    getattr(self, "_" + section_name + "_input").append(
                        (key, {"value": value})
                    )
            except AttributeError:
                pass
        self.scope = scope

    def _get_value(self, section, node_id, xpath, consume=False):
        def _consume_value(infos):
            # This function return the value from infos and set used
            # flags to true if consume flag is set.
            #
            # If a vairalbe is asked, it's more complicated to set the
            # consume flag since a variable can occur several time. We
            # then also consume the dict of variables.
            if section == "_variables_input":
                values = infos['value']
                idx = min(values)
                value = values[idx]
                if consume:
                    value = values.pop(idx)
                    infos['value'] = values
                    if len(values) == 0:
                        infos["used"] = True
            else:
                value = infos['value']
                if consume:
                    infos['used'] = True
            return value

        for (key, infos) in getattr(self, section):
            key_node_id, key_xpath = self._xpath_host(key)
            if xpath == key_xpath:
                if infos.get("used", False):
                    continue
                # Section and xpath part have matched.
                #
                # Next, to get a value, several cases can occur. If
                # the node_id from input file matches the node_id of
                # the current scope, we simply consume the value.
                #
                # If node_id don't match, we assign the node_id to the
                # old_node_id attribute of the current scope node_id
                # and we consume the value.
                #
                # If it doesn't match the node_id, we use old_node_id
                # if it is set.
                if node_id.to_str() == key_node_id:
                    return _consume_value(infos)
                elif node_id.old_is_set() and node_id.old_to_str() == key_node_id:
                    return _consume_value(infos)
                elif node_id.old_is_set() is False:
                    logger.debug("Use old node id: '%s' (instead of '%s')", key_node_id, node_id.to_str())
                    node_id._old_node_id = key_node_id
                    # We create the mapping table between old and new node_id
                    self._mapping_output.append((key_node_id, node_id.to_str()))
                    return _consume_value(infos)

        if node_id.old_is_set():
            msg = ("%s/%s or %s/%s not found in section %s" %
                   (node_id.to_str(), xpath, node_id.old_to_str(), xpath, section))
        else:
            msg = ("%s/%s not found in section %s" %
                   (node_id.to_str(), xpath, section))
        logger.debug(msg)
        raise XpathNotFound(msg)

    def _has_value(self, section, node_id, search_key):
        try:
            self._get_value(section, node_id, search_key)
            return True
        except XpathNotFound:
            return False

    def _get(self, section, node_id, key):
        try:
            return self._get_value(section, node_id, key, consume=True)
        except XpathNotFound:
            return None

    def _xpath_host(self, xpath):
        node_id = xpath.split('/')[0]
        path = "/".join(xpath.split('/')[1:])
        return (node_id, path)

    @property
    def _generic_xpath(self):
        return self.scope._node_id.to_str() + '/' + self.scope.generic_xpath

    @property
    def _xpath(self):
        return self.scope.lfm_host + '/' + self.scope.xpath

    @property
    def manage(self):
        return self._get("_manage_input",
                         self.scope._node_id, self.scope.generic_xpath)

    @manage.setter
    def manage(self, value):
        self._manage_output.append((
            self._generic_xpath,
            {"value": value,
             "used": True})
        )

    @property
    def lfm(self):
        return self._get("_lfm_input",
                         self.scope._node_id, self.scope.generic_xpath)

    @lfm.setter
    def lfm(self, value):
        self._lfm_output.append((
            self._generic_xpath,
            {"value": value,
             "used": True})
        )

    @property
    def specialize(self):
        specialized = self._get("_specialize_input",
                                self.scope._node_id, self.scope.generic_xpath)
        if specialized is not None:
            return self._xpath_host(specialized)
        return (None, None)

    @specialize.setter
    def specialize(self, value):
        self._specialize_output.append((
            self._generic_xpath,
            {"value": self.scope._node_id.to_str() + '/' + value,
             "used": True})
        )

    def multiplicity(self, require_xpath):
        return self._get("_multiplicity_input", self.scope._node_id, require_xpath)

    def multiplicity_setter(self, require_xpath, hosts):
        self._multiplicity_output.append((
            self.scope._node_id.to_str() + "/" + require_xpath,
            {"value": hosts})
        )

    def get_variable(self, xpath):
        variable_value = self._get("_variables_input", self.scope._node_id, xpath)
        if type(variable_value) == dict:
            if len(variable_value) > 1:
                return [value for index, value in variable_value.items()]
            else:
                return variable_value.itervalues().next()
        return variable_value

    def set_variables(self, variables):
        # Add a variable and its value to the variable_list. If the
        # variable already exists in the list, its value is added to
        # the value dict.
        def add_variable(variable_list, variable):
            variable_name = self.scope._node_id.to_str() + '/' + variable.xpath
            for v in variable_list:
                if variable_name == v[0]:
                    v[1]['value'][len(v[1]['value'])] = variable.value
                    return
            variable_list.append((variable_name,
                                  {"value": {0: variable.value},
                                   "used": True}))

        if variables is None:
            return
        for v in variables:
            if v.belongs_provide_ret:
                if not self._has_value("_variables_output_provide_ret", self.scope._node_id, v.xpath):
                    self._variables_output_provide_ret.append((
                        self.scope._node_id.to_str() + '/' + v.xpath,
                        {"value": v.provided_by_xpath,
                         "used": True}))
            elif v.type in ['armonic_host', 'host', 'armonic_this_host', 'armonic_hosts']:
                add_variable(self._variables_output_host, v)
            else:
                if not self._has_value("_variables_output", self.scope._node_id, v.xpath):
                    add_variable(self._variables_output, v)

    def to_primitive(self):
        return {
            "manage": [(k, i["value"]) for k, i in self._manage_output],
            "lfm": [(k, i["value"]) for k, i in self._lfm_output],
            "specialize": [(k, i["value"]) for k, i in self._specialize_output],
            "multiplicity": [(k, i["value"]) for k, i in self._multiplicity_output],
            "variables": [(k, i["value"]) for k, i in self._variables_output],
            "provide_ret": [(k, i["value"]) for k, i in self._variables_output_provide_ret],
            "variables_host": [(k, i["value"]) for k, i in self._variables_output_host],
            "mapping": self._mapping_output
        }


def smart_call(root_provide, values={}):
    """Generator which 'yields' a 3-uple (provide, step,
    optionnal_args)."""

    # We clear all variables used for a deployment
    Provide.Variables = []

    scope = root_provide
    deployment = Deployment(scope, values)

    # The provide call return value.
    ret = None

    logger.info("Smart is using prefilled values: %s" % deployment.to_primitive())

    while True:
        logger.debug("Step: %s - %s" % (scope.step, scope))
        # Stop and Pop conditions
        if scope.step == "done":
            yield (scope, scope.step, None)
        if scope.step == "done" or not scope.manage:
            # If all dependencies of root node have been threated we
            # break the loop
            if not scope.has_requirer():
                break
            # If all dependencies have been threated we
            # go back to its requirer.
            else:
                scope = scope.requirer
                deployment.scope = scope
                continue

        if scope.manage:

            # post_/pre_ step handle
            if scope.step.startswith(('post_', 'pre_')):
                # check do_post_step or do_pre_step
                do_step = getattr(scope, 'do_' + scope.step, None)
                if do_step is not None and do_step() is True:
                    data = yield(scope, scope.step, None)
                    # run on_step
                    on_step = getattr(scope, 'on_' + scope.step, None)
                    if on_step is not None:
                        on_step(data)
                scope._next_step()

            elif scope.step == "manage":
                if scope.do_manage():

                    data = deployment.manage
                    if data is not None:
                        if data:
                            logger.debug("%s is managed from deployment data" % scope.generic_xpath)
                        else:
                            logger.debug("%s is NOT managed from deployment data" % scope.generic_xpath)
                    else:
                        data = yield(scope, scope.step, None)
                    deployment.manage = data

                    scope.on_manage(data)
                scope._test_manage()
                scope._next_step()

            elif scope.step == "lfm":
                host = deployment.lfm

                if scope.do_lfm():
                    if host is not None:
                        data = host
                        logger.debug("%s lfm on %s from deployment data" % (scope.generic_xpath, data))
                    else:
                        data = yield(scope, scope.step, None)
                    scope.on_lfm(data)

                scope._test_lfm()
                deployment.lfm = scope.lfm_host
                scope._next_step()

            elif scope.step == "specialize":
                m = scope.matches()
                logger.debug("Specialize matches: %s" % [p['xpath'] for p in m])

                host, xpath = deployment.specialize

                def specialize(specialized):
                    deployment.specialize = specialized
                    scope.on_specialize(specialized)
                    if scope.manage:
                        scope._build_provide(specialized)
                    scope._build_requires()
                    scope._next_step()

                if xpath is not None:
                    specialized = xpath
                    logger.info("Replay specializes %s with %s" % (scope.generic_xpath, specialized))
                    specialize(specialized)

                elif len(m) > 1 or scope.do_specialize():
                    specialized = yield(scope, scope.step, m)
                    specialize(specialized)
                elif len(m) == 1:
                    specialized = m[0]['xpath']
                    specialize(specialized)
                else:
                    os_type = scope.lfm.info()['os-type']
                    os_release = scope.lfm.info()['os-release']
                    # Go back to the lfm step if specialize doesn't match anything
                    scope._previous_step()
                    # Reset the lfm since we need to choose another one
                    scope.reset_lfm()

                    yield (scope, scope.step, PathNotFound('No path to %s found on %s (%s %s)' % (
                                                           scope.generic_xpath, scope.lfm_host,
                                                           os_type, os_release)))

            elif scope.step == "multiplicity":
                # If no requires are currently managed, we will try to
                # find one (via scope._requirator()). If we are not
                # able to find one, then this step is done and we go
                # to the next step.
                if scope._current_requires is None:
                    try:
                        # We are trying to get a next Requires
                        req = scope._requirator().next()
                        if req.skel.nargs == "*":

                            multiplicity = deployment.multiplicity(req.skel.xpath)
                            if multiplicity is not None:
                                logger.info("Replay sets multiplicity of '%s' to:" % scope.generic_xpath)
                                for m in multiplicity:
                                    logger.info("\t%s" % m)

                            if multiplicity is None:
                                if scope.do_multiplicity():
                                    multiplicity = yield (scope, scope.step, req)
                                multiplicity = scope.on_multiplicity(req, multiplicity)

                            if req.skel.type == 'external':
                                if type(multiplicity) is not list:
                                    raise TypeError("Multiplicity step for external requires must send a list!")
                                number = len(multiplicity)

                            if type(number) is not int:
                                raise TypeError("Multiplicity step must send a integer!")

                            for i in range(0, number):
                                # We build a new Require object from
                                # the skeleton
                                new = req.get_new_require()
                                # We create a new provide child to the
                                # current provide and attach the
                                # require to this provide.
                                p = scope.build_child(
                                    generic_xpath=new.provide_xpath,
                                    child_num=new.child_num,
                                    require=new)
                                new.provide = p
                                if req.skel.type == 'external':
                                    new.provide.lfm_host = multiplicity[i]

                            deployment.multiplicity_setter(req.skel.xpath, multiplicity)
                        else:
                            new = req.get_new_require()
                            p = scope.build_child(
                                generic_xpath=new.provide_xpath,
                                child_num=new.child_num,
                                require=new)
                            new.provide = p

                        scope._current_requires = req

                    except StopIteration:
                        # If all requires have been treated, the
                        # manage_dependencies step is done
                        if scope._current_requires is None:
                            scope._next_step()

                # If a requires is currently managed, we have to
                # process all provide attached to this Requires since
                # it can have a multiplicity greather than 1.
                #
                # We scan this requires to find the next non processed
                # one. If all provides have been processed, then we
                # set the current_requires to None in order to lookup
                # for the next Requires (at next main loop iteration)
                else:
                    done = True
                    for r in scope._current_requires:
                        if r.provide.manage is True and not r.provide.step == "done":
                            done = False
                            scope = r.provide
                            deployment.scope = scope
                            break
                    if done:
                        scope._current_requires = None

            elif scope.step == "validation":
                if scope.do_validation() and not scope.is_validated:
                    # Fill variables with replay file values
                    for variable in scope.variables():
                        variable_value = deployment.get_variable(variable.xpath)
                        if variable_value is not None:
                            variable.value = variable_value
                            logger.debug("Filling '%s' with value '%s' from deployment data" % (variable.xpath, variable_value))
                    data = yield(scope, scope.step, None)
                    if scope.validate(data, static=armonic.common.SIMULATION):
                        # Record variables values
                        deployment.set_variables(scope.variables())
                        scope._next_step()
                else:
                    scope._next_step()

            elif scope.step == "call":
                if scope.do_call():
                    data = yield(scope, scope.step, None)
                    scope.on_call(data)
                if scope.call:
                    scope.lfm_call()
                    if scope.provide_ret is not None:
                        yield (scope, scope.step, scope.provide_ret)
                scope._next_step()

            else:
                yield (scope, scope.step, None)
                scope._next_step()

    yield (None, STEP_DEPLOYMENT_VALUES, deployment.to_primitive())
    return
