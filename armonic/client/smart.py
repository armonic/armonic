"""Smart module offers a high level way to call a provide. Function
:func:`smart_call` generates steps to help the user to

* define LifecycleManager,
* specialize xpath provide,
* specify variable value,
* ...


"""

# Limitiations
#
# It's not able to manage several require (nargs) variable.
# It's not able to manage path

import logging
import copy

logger = logging.getLogger(__name__)


class Variable(object):
    """
    :param from_require: The require that holds this variable.

    """

    def __init__(self, name, from_require, xpath, from_xpath, default, value):
        self.from_require = from_require
        self.name = name
        self.xpath = xpath
        self.from_xpath = from_xpath
        self.default = default
        self._value = value

        # Capture the variable used to resolve self
        self._resolved_by = None

    def copy(self, from_require):
        var = Variable(
            name=self.name,
            from_require=from_require,
            xpath=self.xpath,
            from_xpath=self.from_xpath,
            default=self.default,
            value=self._value)
        
        # All variable are added to a global list
        self.from_require.from_provide.Variables.append(var)

        return var

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        logger.debug("Creating variable %s" % dct_json['xpath'])
        this = cls(dct_json['name'],
                   xpath=dct_json['xpath'],
                   from_xpath=dct_json['from_xpath'],
                   default=dct_json['default'],
                   value=dct_json['default'],
                   **kwargs)
        return this

    @property
    def value(self):
        self._resolve(self.from_require._scope_variables)

        # Be careful, infinite loop is possible. Since this should never
        # happen, we don't avoid it in order to detect it!
        if self._resolved_by is not None:
            return self._resolved_by.value
        else:
            return self._value

    def _resolve(self, scope):
        """Try to assign a value to this variable. If from_xpath is not None,
        it tries to to find back the corresponding
        variable. Otherwise, it tries to find a value in the scope.

        """
        if self._value is not None:
            return

        # If the variable is host, try to find it from called provide
        if self.name == 'host' and self._value is None:
            if self.from_require.type == 'external':
                if self.from_require.provide is not None:
                    self._value = self.from_require.provide.host
                    # FIXME: We have a problem because host doesn't come from a variable!
                    self._resolved_by = None
            return

        # If the variable has a from_xpath attribute,
        # try to find back its value
        if self.from_xpath is not None:
            for v in self.from_require.from_provide.Variables:
                if v.xpath == self.from_xpath:
                    self._resolved_by = v
                    logger.debug("Variable [%s] value comes from [%s] with value %s" %(
                        self.xpath, v.xpath, v._value))
                    return
            logger.info("Variable [%s] from_xpath [%s] not found" % (
                self.xpath, self.from_xpath))

        if self.from_require.special:
            return

        if self.from_xpath is None:
            for v in scope:
                if self.name == v.name:
                    logger.debug("Variable [%s] resolved by [%s] with value %s" %(
                        self.xpath, v.xpath, v._value))
                    self._resolved_by = v

    def pprint(self):
        return {"name": self.name,
                "xpath": self.xpath,
                "default": self.default,
                "value": self.value}

    def __repr__(self):
        if self._resolved_by is not None:
            resolved_by = self._resolved_by.xpath
        else:
            resolved_by = None
        return "Variable(%s, name=%s, value=%s, xpath=%s, resolved_by=%s)" % (
            id(self),
            self.name,
            self._value,
            self.xpath,
            resolved_by)


class Requires(list):
    """This class is used to represent the require multiplicity."""
    def __init__(self, skel):
        self.skel = skel

    def append(self):
        new = self.skel.copy()
        list.append(self, new)
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
        self.from_provide = from_provide
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
            new.provide_args.append(v.copy(new))
            new._scope_variables.append(v)

        new.provide_ret = []
        for v in self.provide_ret:
            new.provide_ret.append(v.copy(new))
            new._scope_variables.append(v)

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
            this._scope_variables.append(var)

        # Here, we add provide ret variable.
        this.provide_ret = []
        for v in dct_json['provide_ret']:
            var = Variable.from_json(v, from_require=this)
            this.provide_ret.append(var)

            # This variable is added to the scope.
            this._scope_variables.append(var)

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
        return self.provide_args + self.provide_ret

    def update_provide_ret(self, provide_ret):
        for (name, value) in provide_ret.items():
            for v in self.provide_ret:
                if v.name == name:
                    v._value = value
                    logger.debug("Variable %s has been updated with value "
                                 "'%s' from provide_ret" % (v.xpath, value))
                    logger.debug("%s", id(v))
                    break


class Provide(object):
    """This class describe a provide and its requires and remotes requires
    contains provide. Thus, this object can describe a tree. To build
    the tree, the function :func:`smart_call` must be used.

    To adapt the behavior of this class, redefine methods on_step and
    do_step, where step is manage, lfm, specialize, etc.
    If method do_step returns True, this step is 'yielded'.
    Method on_step takes as input the sent data.

    :param child_number: if this Provide is a dependancies, this is
    the number of this child.
    :param requirer: the provide that need this require
    :param require: the remote require of the requirer that leads
                    to this provide.

    """
    STEPS = ["manage",
             "lfm",
             "specialize",
             "set_dependancies",
             "multiplicity",
             "validation",
             "call",
             "done"]

    # Contains all variables. This is used to find back from_xpath value.
    Variables = []

    require = None
    """Contains the :class:`Require` that requires this provide."""

    requirer = None
    """Contains the :class:`Provide` that requires this current
    provide."""

    def __init__(self, generic_xpath, requirer=None,
                 child_num=None, require=None):
        self.generic_xpath = generic_xpath
        self.requirer = requirer
        self.require = require

        # This dict contains variables that belongs to this scope.
        self._scope_variables = {}

        if requirer is not None:
            self.depth = requirer.depth + 1
            self.tree_id = []
            for i in requirer.tree_id:
                self.tree_id.append(i)
            self.tree_id.append(child_num)

        else:
            self.depth = 0
            self.tree_id = [0]

        #self.ignore = False
        self._step_current = 0

        self._current_require = None
        self._children_generator = None

        # Contain all requires. A require can be several time in this
        # list due to multiplicity.
        self._requires = None

        # Provide configuration variables.
        #
        # If this provide comes from a local require, the lfm is taken
        # from the requirer.
        if (require is not None and
                require.type == "local"):
            self.lfm = requirer.lfm
        else:
            self.lfm = None

        self.manage = True
        self.call = None
        self.specialized_xpath = None

        # Attribute host is required for external Provide
        self.host = None

    def __repr__(self):
        return "<Provide(%s)>" % self.generic_xpath

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

    def has_requirer(self):
        """To know if it is the root provide."""
        return self.requirer is not None
 
    @property
    def step(self):
        return Provide.STEPS[self._step_current]
        
    def _next_step(self):
        if self._step_current+1 > len(Provide.STEPS)-1:
            raise IndexError
        self._step_current += 1

    def _build_require_from_call_require(self, dct_json):
        """From a json dict, build Require and Remote require."""
        self.remotes = []
        self.requires = []
        idx = 0
        for p in dct_json:
            special = p['name'] in ['enter', 'leave', 'cross']
            for require in p['requires']:
                if require['type'] in ['external', 'local']:
                    self.remotes.append(Requires(Remote.from_json(
                        require, special=special, child_num=idx, from_provide=self)))
                elif require['type'] in ['simple']:
                    requires = Requires(Require.from_json(
                        require, special=special, child_num=idx, from_provide=self))
                    requires.append()
                    self.requires.append(requires)
                idx += 1
                
    def _build_requires(self):
        """Get all requires"""
        provides = self.lfm.provide_call_requires(self.specialized_xpath)
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
        ret = self.__class__(generic_xpath=generic_xpath,
                             requirer=self,
                             child_num=child_num,
                             require=require)
        return ret

    def do_lfm(self):
        """The step lfm is applied if it returns True."""
        return self.lfm is None

    def on_lfm(self, lfm):
        self.lfm = lfm

    def _test_lfm(self):
        if self.lfm is None:
            raise AttributeError("'lfm' attribute must not be None. Must be set at 'lfm' step")

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

    def do_set_dependancies(self):
        """Return False by default."""
        return False

    def on_set_dependancies(self, call):
        pass

    def do_manage(self):
        return True

    def on_manage(self, data):
        self.manage = data

    def _test_manage(self):
        if self.manage is None:
            raise AttributeError("'manage' attribute must not be None. Must be set at 'manage' step")

    def matches(self):
        """Return the list of xpaths that matched the generic_xpath"""
        return self.lfm.uri(xpath=self.generic_xpath, relative=True)

    def on_specialize(self, xpath):
        """Used to specialize the generic_xpath. You must define
        self.specialized_xpath."""
        self.specialized_xpath = xpath

    def do_specialize(self):
        """Specialization can not be avoided. If the provide matches only 1
        xpath, yield doesn't occurs if this method returns False.

        Thus, by returning True, specialization always yields.

        """
        return False

    def update_scope_provide_ret(self, provide_ret):

        """When the provide call returns value, we habve to update the scope
        of the require in order to be able to use these value to fill
        depending provides.
        """
        # A provide should ALWAYS return a dict.
        if type(self.provide_ret) is dict:  # FIXME
            self.require.update_provide_ret(self.provide_ret)

    def lfm_call(self):
        # FIXME. This is a temporary hack!
        ret = self.lfm.provide_call_validate(
            provide_xpath_uri=self.specialized_xpath,
            requires=self.variables_serialized())
        if ret['errors']:
            import pprint
            print "Variables used are"
            pprint.pprint(self.Variables) 
            print "Variable not validated"
            pprint.pprint(ret)
            print "Error: Variables are not been validated!"
            exit(1)

        self.provide_ret = self.lfm.provide_call(
            provide_xpath_uri=self.specialized_xpath,
            requires=self.variables_serialized())

        self.update_scope_provide_ret(self.provide_ret)
        # self.provide_ret = self.lfm.call("provide_call_validate",
        #                                  provide_xpath_uri=self.specialized_xpath,
        #                                  requires=self.variables_serialized())
        # from pprint import pprint
        # pprint(self.provide_ret)


def smart_call(root_provide):
    """Return a generator which 'yields' a 3-uple (provide, step,
    optionnal_args)."""

    scope = root_provide
    while True:
        logger.debug("Step: %s - %s" % (scope.step, scope))
        # Stop and Pop conditions
        if scope.step == "done":
            yield (scope, scope.step, None)
        if scope.step == "done" or not scope.manage:
            # If all dependencies of root node have been threated we
            # break the loop
            if scope.requirer == None:
                break
            # If all dependencies have been threated we
            # go back to its requirer.
            else:
                scope = scope.requirer
                continue

        if scope.manage:
            if scope.step == "manage":
                if scope.do_manage():
                    data = yield (scope, scope.step, None)
                    scope.on_manage(data)
                scope._test_manage()
                scope._next_step()

            elif scope.step == "lfm":
                if scope.do_lfm():
                    data = yield(scope, scope.step, None)
                    scope.on_lfm(data)
                scope._test_lfm()
                scope._next_step()

            elif scope.step == "set_dependancies":
                if scope.do_set_dependancies():
                    data = yield(scope, scope.step, None)
                    scope.on_set_dependancies(data)
                scope._build_requires()
                scope._next_step()

            elif scope.step == "validation":
                yield(scope, scope.step, None)
                scope._next_step()

            elif scope.step == "call":
                if scope.do_call():
                    data = yield(scope, scope.step, None)
                    scope.on_call(data)
                if scope.call:
                    scope.lfm_call()
                scope._next_step()

            elif scope.step == "specialize":
                m = scope.matches()
                logger.debug("Specialize matches: %s" % m)
                if len(m) > 1 or scope.do_specialize():
                    specialized = yield(scope, scope.step, m)
                elif len(m) == 1:
                    specialized = m[0]
                else:
                    raise Exception(
                        "Xpath '%s' matches nothing!" % scope.generic_xpath)
                scope.on_specialize(specialized)
                scope._next_step()

            elif scope.step == "multiplicity":
                if scope._current_require is None:
                    # For each require, provides are built
                    try:
                        # Get the next require to manage
                        req = scope._requirator().next()
                        if req.skel.nargs == "*":
                            number = yield (scope, scope.step, req)
                            for i in range(0,number):
                                new = req.append()
                                p = scope.build_child(
                                    generic_xpath=new.provide_xpath,
                                    child_num=new.child_num,
                                    require=new)
                                new.provide = p
                        else:
                            new = req.append()
                            p = scope.build_child(
                                generic_xpath=new.provide_xpath,
                                child_num=new.child_num,
                                require=new)
                            new.provide = p
                        scope._current_require = req

                    except StopIteration:
                        pass

                    # If all requires have been treated, the
                    # manage_dependancies step is done
                    if scope._current_require is None:
                        scope._next_step()
                       
                else:
                    done = True
                    for r in scope._current_require:
                        if r.provide.manage == True and not r.provide.step == "done":
                            done = False
                            scope = r.provide
                            break
                    if done:
                        scope._current_require = None
            else:
                yield (scope, scope.step, None)
                scope._next_step()

