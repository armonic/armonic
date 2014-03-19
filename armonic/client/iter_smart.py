# Limitiations
# 
# It's not able to manage several require (nargs) variable.
# It's not able to manage path

import logging

logger = logging.getLogger(__name__)

class Variable(object):
    """
    :param from_require: The require that holds this variable.

    """

    def __init__(self, name, from_require):
        self.from_require = from_require
        self.name = name
        
        # All variable are added to a global list
        self.from_require.from_provide.Variables.append(self)

        self._value = None

    @property
    def value(self):
        if self._value is None:
            self._resolve(self.from_require.from_provide._scope_variables)
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        logger.debug("Creating variable %s" % dct_json['xpath'])
        this = cls(dct_json['name'], **kwargs)
        this.xpath = dct_json['xpath']
        this.from_xpath = dct_json['from_xpath']
        this.default = dct_json['default']
        this.value = this.default

        # Add this variable to the scope
        if this.value is not None:
            this.from_require.from_provide._scope_variables[this.name] = this

        return this

    def _resolve(self, scope):
        """Try to assign a value to this variable. If from_xpath is not None,
        it tries to to find back the corresponding
        variable. Otherwise, it tries to find a value in the scope.

        """
        # If the variable has a from_xpath attribute,
        # try to find back its value
        if self.from_xpath is not None:
            for v in self.from_require.from_provide.Variables:
                if v.xpath == self.from_xpath:
                    self._value = v.value
                    logger.debug("Variable [%s] value comes from [%s] with value %s" %(
                        self.xpath, v.xpath, v.value))
                    return
            logger.info("Variable [%s] from_xpath [%s] not found" %(
                self.xpath, self.from_xpath))
            
        # If the variable is host, try to find it from called provide
        if self.name == 'host' and self._value is None:
            if self.from_require.type == 'external':
                try:
                    self._value = self.from_require.provides[0].host
                except IndexError:
                    pass

        # Try to assign a value from the provide scope
        if self.name in scope:
            logger.debug("Variable [%s] resolved by [%s] with value %s" %(
                self.xpath, scope[self.name].xpath, scope[self.name].value))
            self._value = scope[self.name].value


    def pprint(self):
        return {"name": self.name,
                "xpath": self.xpath,
                "default": self.default,
                "value": self.value}


class Require(object):
    """
    :param from_provide: The provide that holds this require.

    """

    def __init__(self, from_provide, child_num):
        self.child_num = child_num
        self.from_provide = from_provide
    

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        this = cls(**kwargs)
        this.xpath = dct_json['xpath']
        this.type = dct_json['type']
        
        this._variables = []
        for v in dct_json['variables_skel']:
            this._variables.append(Variable.from_json(v, from_require=this))
            
        this.json = dct_json
        return this

    def pprint(self):
        return {"xpath": self.xpath,
                "variables": [v.pprint() for v in self._variables]}

    def get_variables(self):
        """To get a list of all variables which can be submitted to
        provide_call_validate"""
        acc = []
        for v in self._variables:
            acc.append((v.xpath, {0: v.value}))
        return acc

    def variables(self):
        """:rtype: [:class:`Variable`]"""
        return self._variables


class Remote(Require):
    def __init__(self, from_provide, child_num):
        self.child_num = child_num
        self.from_provide = from_provide
        self.provides = []

    @classmethod
    def from_json(cls, dct_json, **kwargs):
        this = cls(**kwargs)
        this.xpath = dct_json['xpath']
        this.type = dct_json['type']
        this.nargs = dct_json['nargs']
        this.provide_xpath = dct_json['provide_xpath']
        this.provide_args = []
        for v in dct_json['provide_args']:
            this.provide_args.append(Variable.from_json(v, from_require=this))
        
        this.json = dct_json
        return this

    def pprint(self):
        return {"xpath": self.xpath,
                "variables": [v.pprint() for v in self.provide_args]}

    def get_variables(self):
        acc = []
        for v in self.provide_args:
            acc.append((v.xpath, {0: v.value}))
        return acc

    def variables(self):
        """:rtype: [:class:`Variable`]"""
        return self.provide_args


class Provide(object):
    """

    :param child_number: if this Provide is a dependancies, this is
    the number of this child.
    :param requirer: the provide that need this require
    :param require: the remote require of the requirer that leads to this provide.
    """
    STEPS = ["manage", 
             "lfm",
             "specialize",
             "set_dependancies",
             # This is a private step
             "multiplicity", 
             "validation",
             "call",
             "done"]

    # Contains all variables. This is used to find back from_xpath value.
    Variables = []

    def __init__(self, generic_xpath, requirer=None, child_num=None, require=None):
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

            # We copy variables dict from parent the scope.
            # They will be upgraded when requires are built.
            for (k, v) in requirer._scope_variables.items():
                self._scope_variables[k] = v
                
            
        else:
            self.depth = 0
            self.tree_id = [0]

        self.ignore = False
        self._step_current = 0

        self._current_require = None
        self._children_generator = None

        # Provide configuration variables.
        #
        # If this provide comes from a local require, the lfm is taken
        # from the requirer.
        if ((require is not None and 
             require.type == "local")):
            self._lfm = requirer.lfm
        else:
            self._lfm = None

        self._manage = None
        self._call = None

        # Attribute host is required for external Provide
        self.host = None


    def get_variables(self):
        """Get variables in the format for provide_call"""
        acc = []
        for r in self.remotes + self.requires:
            acc += r.get_variables()
        return acc
        
    def variables(self):
        """:rtype: [:class:`Variable`]"""
        acc = []
        for v in self.remotes + self.requires:
            acc += v.variables()
        return acc

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


    def build_require_from_call_require(self, dct_json):
        """From a json dict, build Require and Remote require."""
        self.remotes = []
        self.requires = []
        idx = 0
        for p in dct_json:
            for require in p['requires']:
                if require['type'] in ['external', 'local']:
                    self.remotes.append(Remote.from_json(require, child_num=idx, from_provide=self))
                elif require['type'] in ['simple']:
                    self.requires.append(Require.from_json(require, child_num=idx, from_provide=self))
                idx += 1

    def build_requires(self):
        """Get all requires"""
        provides = self.lfm.provide_call_requires(self.specialized_xpath)
        self.build_require_from_call_require(provides)
                    
    def requirator(self):
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

    @property
    def lfm(self):
        return self._lfm
    @lfm.setter
    def lfm(self, lfm):
        self._lfm = lfm
        
    def do_lfm(self):
        """The step lfm is applied if it returns True."""
        return self._lfm is None

    def on_lfm(self, lfm):
        self._lfm = lfm

    def _test_lfm(self):
        if self._lfm is None:
            raise AttributeError("'lfm' attribute must not be None. Must be set at 'lfm' step")

    @property
    def manage(self):
        """If it returns None, walk function yields."""
        return self._manage
        
    @manage.setter
    def manage(self, manage):
        """Set true if this provide has to be managed"""
        self._manage = manage
        # Used to stop the genreator
        self.ignore = not manage

    @property
    def call(self):
        """If it returns None, walk function yields."""
        return self._call
        
    @call.setter
    def call(self, call):
        """Set true if this provide has to be called"""
        self._call = call

    def matches(self):
        """Return the list of xpaths that matched the generic_xpath"""
        return self.lfm.uri(xpath=self.generic_xpath)

    def specialize(self, xpath):
        """Used to specialize the generic_xpath"""
        self.specialized_xpath = xpath
    
    def lfm_call(self):
        self.provide_ret = self.lfm.provide_call(
            provide_xpath_uri=self.specialized_xpath,
            requires=self.get_variables())
        # self.provide_ret = self.lfm.call("provide_call_validate",
        #                                  provide_xpath_uri=self.specialized_xpath,
        #                                  requires=self.get_variables())
        # from pprint import pprint
        # pprint(self.provide_ret)


def walk(root_scope):
    """Return a generator which 'yields' a 3-uple (provide, step,
    optionnal_args)."""

    scope = root_scope
    while True:
        # Stop and Pop conditions
        if scope.step == "done":
            yield (scope, scope.step, None)
        if scope.step == "done" or scope.ignore:
            # If all dependencies of root node have been threated we
            # break the loop
            if scope.requirer == None:
                break
            # If all dependencies have been threated we
            # go back to its requirer.
            else:
                scope = scope.requirer
                continue

        if not scope.ignore:
            if scope.step == "manage":
                if scope.manage is None: 
                    scope.manage = yield (scope, scope.step, None)
                scope._next_step()

            elif scope.step == "lfm":
                if scope.do_lfm():
                    data = yield(scope, scope.step, None)
                    scope.on_lfm(data)
                    scope._test_lfm()
                scope._next_step()

            elif scope.step == "set_dependancies":
                scope.build_requires()
                #yield(scope, scope.step, None)
                scope._next_step()

            elif scope.step == "validation":
                yield(scope, scope.step, None)
                scope._next_step()

            elif scope.step == "call":
                if scope.call is None:
                    scope.call = yield(scope, scope.step, None)
                if scope.call:
                    scope.lfm_call()
                scope._next_step()

            elif scope.step == "specialize":
                m = scope.matches()
                if len(m) > 1:
                    specialized = yield(scope, scope.step, m)
                else:
                    specialized = m[0]
                scope.specialize(specialized)
                scope._next_step()

            elif scope.step == "multiplicity":
                if scope._current_require is None:
                    # For each require, provides are built
                    try:
                        # Get the next require to manage
                        req = scope.requirator().next()
                        req.provides = []
                        if req.nargs == "*":
                            number = yield (scope, scope.step, req)
                            for i in range(0,number):
                                req.provides.append(scope.build_child(
                                    generic_xpath=req.provide_xpath, 
                                    child_num=req.child_num,
                                    require=req))
                        else:
                            req.provides.append(scope.build_child(
                                generic_xpath=req.provide_xpath, 
                                child_num=req.child_num,
                                require=req))
                        scope._current_require = req
                    except StopIteration:
                        pass

                    # If all requires have been treated, the
                    # manage_dependancies step is done
                    if scope._current_require is None:
                        scope._next_step()
                       
                else:
                    done = True
                    for p in scope._current_require.provides:
                        if p.ignore == False and not p.step == "done":
                            done = False
                            scope = p
                            break
                    if done:
                        scope._current_require = None
            else: 
                yield (scope, scope.step, None)
                scope._next_step()

