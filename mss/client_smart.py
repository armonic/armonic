"""
1) User wants to call a provide.
   For instance, Wordpress.get_site
2) If this provide requires other provides (local or external), they are called.
   Suppose that Wordpress.get_site requires Mysql.addDatabase provide
2.1) We ask user if she really wants Mysql.addDatabase.
     If she doesn't, we continue to next Require.
2.2) We fill Requires of Mysql.addDatabase with (in order):
     0) If a Require needs a provide, go to 1)
     1) Values specified by require Mysql.addDatabase of provide Wordpress.get_site
     2) Default values of Requires of Mysql.addDatabase provide
     3) Missing values are asked to user.
2.3) We ask user if she still wants to call provide Mysql.addDatabase
     If true, we call it


3) Requires are filled with provide args and provide ret


NOTE for dev: Maybe we should make recursion on requires instead of
Provide. This means that we should add some methods to Require
class. Maybe this would permit to do the provide call on agent if
required ...

"""
#import mss.modules.mysql as mysql
from mss.lifecycle import LifecycleManager
from mss.common import load_lifecycles, ValidationError
from mss.require import RequireNotFilled
from mss.client_socket import ClientSocket
import readline

from itertools import repeat
load_lifecycles("modules")

lf_manager = ClientSocket(host="192.168.122.39")

Variables=[]

import sys
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if len(sys.argv) > 1:
    if sys.argv[1] == 'debug':
        logger.setLevel(logging.DEBUG)

class ShowAble(object):
    def sep(self,offset=0):
        if self.depth + offset == 0:
            return ""
#        return str(self.depth)+"/"+str(offset)+"".join(repeat("    ",self.depth+offset))
        return "".join(repeat("    ",self.depth+offset))

    def show(self,str,indent=0):
        print "%s%s" % (self.sep(offset=indent) , str)


class Provide(ShowAble):
    #Contain user specified require classes.
    _require_classes = {}


    def __init__(self, lf_name, provide_name, host=None, requires=None,  caller_provide=None, suggested_args=[], depth=0):
        """

        To fill a require, we can use several set of value:

        - Values specified by the require that calls this provide are available in self.suggested_args
        -

        :param caller_provide: Name of provide that called this one.
        :param suggested_args: Suggested args provided by the caller.
        :type suggested_args: List of Variable.
        """

        self.lf_name=lf_name
        self.provide_name=provide_name
        self.requires=requires
        self.suggested_args=suggested_args
        self.host = host
        self.depth = depth
        self.caller_provide = caller_provide

        # This is filled by self.call(). This contains the dict of
        # returned value by this provide.
        self.provide_ret = {}


    def handle_call(self):
        """To validate that the inferred provide should be called.

        :rtype: bool. Return True if the provide must be called, false otherwise.
        """
        self.show("Preparing the call of provide %s.%s..." % (self.lf_name,self.provide_name))
        msg = "Where do you want to call it?"
        ret = user_input_variable(prefix=self.sep(), variable_name = 'host', message = msg, prefill = self.caller_provide.host)
        host = ret['host']
        self.host = host
        msg = ("Do you really want to call %s.%s on '%s' ?" % (
                self.lf_name,
                self.provide_name,
                host))
        return user_input_yes(msg, prefix=self.sep())


    def get_requires(self):
        logger.debug("%sRequires needed to call provide %s.%s:"  % (
            self.sep(0),
            self.lf_name,
            self.provide_name))
        self.lf_manager = ClientSocket(host=self.host)
        self.provide_call_requires = self.lf_manager.call("provide_call_requires",self.lf_name, self.provide_name)
        self.provide_requires = self.lf_manager.call("provide_call_args",self.lf_name, self.provide_name)
        self.requires = self.provide_call_requires + self.provide_requires

    def call(self):
        if self.handle_call():
            self._build_requires()
            self.show("Provide '%s' will be called with Requires:" % (self.provide_name))
            for r in self.requires:
                self.show("%s" % (r.name) , indent=1)
                self.show("%s" % (r.get_values()) , indent = 2)
            user_input_yes("Confirm the call?", prefix=self.sep())

            provide_requires_primitive = self._generate_requires_primitive(self.provide_call_requires)
            provide_args_primitive = self._generate_requires_primitive(self.provide_requires)
            logger.debug("mss.call(%s, %s, %s, %s)" % (
                    self.lf_name,
                    self.provide_name,
                    provide_requires_primitive,
                    provide_args_primitive))
            self.lf_manager.call("provide_call",
                                        self.lf_name,
                                        self.provide_name,
                                        provide_requires_primitive,
                                        provide_args_primitive)
        return {}

    def _generate_requires_primitive(self,require_list):
        """From a require list, generate suitable require dict to be
        passed to provide_call function.

        :type require_list: [Require]
        :rtype: {require1: {variable1:v1,...}, ...}
        """
        ret = {}
        for r in require_list:
            ret.update({r.name: r.get_values()})
        return ret

    def _build_requires(self):
        """This method makes the recursion. If external or local
        Require are required, we build a provide, call it and use its
        values to fill the Require."""

        self.get_requires()
        requires_external = [r for r in self.requires if r.type == "external"]
        requires_simple = [r for r in self.requires if r.type == "simple"]
        requires_user = [r for r in self.requires if r.type == "user"]
        requires_local = [r for r in self.requires if r.type == "local"]

        for r in (requires_external + requires_local):
            if self._require_classes.has_key(r.type):
                r.__class__ = self._require_classes[r.type]
            r._build(self)

        for r in (requires_simple + requires_user):
            if self._require_classes.has_key(r.type):
                r.__class__ = self._require_classes[r.type]
            r._build(self)


    @classmethod
    def set_require_class(cls, require_type, klass):
        cls._require_classes.update({require_type : klass})


################################################################################
#                                  REQUIRE CLASSES                             #
################################################################################

import mss.require

class Require(object):
    """
    To fill this require, you can use::
    
    - Arguments specified by the require : require.provide_args
    - Arguments used to call the provide : ~provide_requires[*].values
    - Default values of requires of this provide : ~provide_requires[*].defaults
    """

    def build_values(self):
        raise NotImplementedError

    def build_save_variables(self):
        """Redefine it to save require variables."""
        raise NotImplementedError

    def on_require_not_filled_error(self,err_variable,values):
        raise NotImplementedError

    def on_validation_error(self,err_variable,values):
        raise NotImplementedError

    def _build(self,provide_caller):
        self.provide_caller = provide_caller
        self.depth = provide_caller.depth
        # We validate this require with values returned by provide.

        ret = self.build_values()
        self._build_validate(ret)

        self.build_save_variables()

    def _build_validate(self,values):
        while True:
            try:
                self.fill(values)
                self.validate()
            except RequireNotFilled as e:
                values = self.on_require_not_filled_error(e.variable_name,values)
                continue
            except ValidationError as e:
                values = self.on_validation_error(e.variable_name,values)
                continue
            break



class RequireSimple(mss.require.Require,ShowAble):
    def _build(self,provide_caller):
        logger.debug("Handle simple require %s" % self.name)
        #print "Suggested args: %s" % self.suggested_args
        #print "Required args: %s" % self.get_values()
        needed = self.get_values()
        suggested = dict([(s.name,s.value) for s in provide_caller.suggested_args])
        ret = update_empty(needed,suggested)

        self.fill(ret)
        self.validate()
        logger.debug("Require %s of provide %s has be filled with :"%(self.name,provide_caller.provide_name))
        logger.debug(ret)
        for v in self.variables:
            Variables.append((v.full_name, v.value))
        return ret

class RequireUser(mss.require.RequireUser, Require, ShowAble):
    def build_values(self):
        # Here we generate require value
        for (name,value) in Variables:
            if self.provided_by == name:
                return {self.variables[0].name : value}

    def build_save_variables(self):
        """Redefine it to save require variables."""
        Variables.append((self.variables[0].full_name , self.variables[0].value))


class RequireWithProvide(Require):
    def _provide_call(self):
        self.provide = Provide(lf_name = self.lf_name,
                               provide_name = self.provide_name,
                               caller_provide = self.provide_caller,
                               suggested_args = self.provide_args,
                               depth = self.depth+1)
        # Maybe, we don't want to call the proposed require. Moreover,
        # we have to choose the provide host.
        self.provide.call()
    
    def build_save_variables(self):
        """Redefine it to save require variables."""
        for v in self.variables[0]:
            Variables.append((v.full_name, v.value))

    def build_values(self):
        # We call the provide to get its return values
        self._provide_call()

        # Here we generate require value
        ret = update_empty(self.get_values(), self.provide.provide_ret)
        logger.debug(ret)
        return ret

class RequireLocal(mss.require.RequireLocal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep(), prefill=self.provide.host))
        return values

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide_name,
            err_variable, ret[err_variable])
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg))

class RequireExternal(mss.require.RequireExternal, RequireWithProvide, ShowAble):
    def on_require_not_filled_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' is not set.\nPlease set it:"%(err_variable, self.name, self.provide_name)
        values.update(user_input_variable(variable_name = err_variable, message = msg, prefix=self.sep(), prefill=self.provide.host))
        return values

    def on_validation_error(self,err_variable,values):
        msg = "Variable '%s' of require '%s' of provide '%s' has been set with wrong value.\n'%s' = '%s'\nPlease change it:"%(
            err_variable, self.name, self.provide_name,
            err_variable, ret[err_variable])
        values.update(user_input_variable(variable_name = err_variable, prefix=self.sep(), message = msg))
        




################################################################################
#                            HELPERS                                           #
################################################################################

def user_input_yes(msg, prefix=''):
    answer = raw_input("%s%s\n%s[Y]/n: " % (prefix, msg ,prefix))
    if answer == 'n':
        return False
    return True

def user_input_variable(variable_name, message, prefix="", prefill=""):
    """
    :param variable_name: The name of the variable that user must set
    :param message: A help message
    :rtype: {variable_name:value}
    """
    prompt = "%s%s\n%s%s = " % (prefix, message, prefix, variable_name)
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return {variable_name:raw_input(prompt)}
    finally:
        readline.set_startup_hook()

def update_empty(origin,*dcts):
    """Take a origin dict with some values equal to None. Fill these
    value with values from other dicts.

    Example:
    update_empty({'a':1,'b':None,'c':2}, {'a':4, 'b':1}, {'c':4, 'b':2})
    >> {'a': 1, 'c': 2, 'b': 1}
    """
    for (ko,vo) in origin.items():
        if vo == None:
            found = False
            for d in dcts:
                if found:
                    break
                for (k,v) in d.items():
                    if k == ko:
                        origin.update({k:v})
                        found = True
                        break
    return origin



Provide.set_require_class("external",RequireExternal)
Provide.set_require_class("simple",RequireSimple)
Provide.set_require_class("local",RequireLocal)
Provide.set_require_class("user",RequireUser)

class ProvideUser(object):
    host = "192.168.123.2"

p = Provide(lf_name='Wordpress', provide_name='get_site', caller_provide=ProvideUser())
p.call()

for v in Variables:
    print v
