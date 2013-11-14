"""
Overview
^^^^^^^^

This module permits to call a provide, fill its requires and
recursively call provide if external or local requires are specified.

In fact, this is just a skeleton. Thus, it offers some classes that
can be redefined to adapt the behavior to what the user want. For an
implementation of this module, see mss3-smart.

To implement a smart client, you have to redefine :class:`Provide` and
:class:`Require`.

How to works::

1. User wants to call a provide.
   For instance, Wordpress.get_site
2. If this provide requires other provides (local or external), they will be called.
   For instance, suppose that Wordpress.get_site requires Mysql.addDatabase provide

   a. We ask user if she really wants Mysql.addDatabase.
      If she doesn't, we continue to next Require.
   b. We fill Requires of Mysql.addDatabase with (in order)

     a. If a Require needs a provide, go to '1.'
     b. Values specified by require Mysql.addDatabase of provide Wordpress.get_site
     c. Default values of Requires of Mysql.addDatabase provide
     d. Missing values are asked to user.
3. We ask user if she still wants to call provide Mysql.addDatabase
   If true, we call it


4. Requires are filled with provide args and provide ret


NOTE for dev: Maybe we should make recursion on requires instead of
Provide. This means that we should add some methods to Require
class. Maybe this would permit to do the provide call on agent if
required ...

Code documentation
^^^^^^^^^^^^^^^^^^

"""
#import mss.modules.mysql as mysql
from mss.lifecycle import LifecycleManager
from mss.common import load_lifecycles, ValidationError
from mss.require import RequireNotFilled
from mss.client_socket import ClientSocket
import readline

from itertools import repeat
load_lifecycles("modules")

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
    """This class describes a Provide and permit to fill its require
    by creating instances of :class:`Require`.

    To use this class, we have to ::

    - redefine method :py:meth:`Provide.handle_call`,
    - redefine method :py:meth:`Provide.confirm_call`,
    - attach specialised Require classes to require type by using the static method :py:meth:`set_require_class`.

    By redefining this class, you can control the host where the
    provide (via :py:meth:`Provide.handle_call`) will be called, and
    control if the provide has to be call or not (via
    :py:meth:`Provide.confirm_call`).


    Note: A provide name should not be defined with a lifecycle name
    because in the future, the user will be able to choose a lifecycle
    that offers this provide.


    :param lf_name: Name of provide's lifecycle 
    :type lf_name: String
    :param provide_name: Name of the provide
    :type provide_name: String
    :param host: Host where the provide has to be call
    :type host: String

    :param caller_provide: Name of provide that called this one.
    :type caller_provide: Subclass of :class:`Provide`

    :param suggested_args: Suggested args provided by the caller. This\
    corresponds to the require (that expect this provide) variables.
    :type suggested_args: List of Variable.
    :param depth: The depth in provide call tree
    :type depth: Integer
    """

    #Contain user specified require classes.
    _require_classes = {}


    def __init__(self, lf_name, provide_name, host=None, caller_provide=None, suggested_args=[], depth=0):
        self.lf_name=lf_name
        self.provide_name=provide_name
        self.requires=None
        self.suggested_args=suggested_args
        self.host = host
        self.depth = depth
        self.caller_provide = caller_provide

        # This is filled by self.call(). This contains the dict of
        # returned value by this provide.
        self.provide_ret = {}


    def handle_call(self):
        """Redefine it to validate that the inferred provide should be called.
        Moreover, you can set the host variable of this provide.

        :rtype: Return True if the provide must be called, false otherwise
        """
        raise NotImplementedError

    def confirm_call(self):
        """Redefine it to confirm the provide call after that requires has been filled.

        :rtype: boolean"""
        raise NotImplementedError

    def _get_requires(self):
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
            
            if self.confirm_call():
                provide_requires_primitive = self._generate_requires_primitive(self.provide_call_requires)
                provide_args_primitive = self._generate_requires_primitive(self.provide_requires)
                logger.debug("mss.call(%s, %s, %s, %s)" % (
                        self.lf_name,
                        self.provide_name,
                        provide_requires_primitive,
                        provide_args_primitive))
                return self.lf_manager.call("provide_call",
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

        self._get_requires()
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
        """Use this method to specify which Require subclass has to be
        used for a require type."""
        cls._require_classes.update({require_type : klass})


################################################################################
#                                  REQUIRE CLASSES                             #
################################################################################

import mss.require

class Require(object):
    """
    This class has to be used to handle how a require is built.
    So, basically we have to handle :
    
    - how values of a require are built (see :py:meth:`Require.build_values`)
    - what happen if a variable is not filled (see :py:meth:`Require.on_require_not_filled_error`)
    - what happen if a variable is not validated (see :py:meth:`Require.on_validation_error`)
    - how values used to fill this require are saved (see :py:meth:`Require.build_save_to`)

    DOC TODO :To build value of this require, several object are available

    To fill this require, you can use::
    
    - Arguments specified by the require : require.provide_args
    - Arguments used to call the provide : ~provide_requires[*].values
    - Default values of requires of this provide : ~provide_requires[*].defaults
    """

    def build_values(self):
        """Redefine it to build the value that has been used by this requires.
        
        :rtype: A dict of variable name and values.
        """
        raise NotImplementedError

    def on_require_not_filled_error(self,err_variable,values):
        """This method is called when a variable is not filled. Redefine it to adapt its behavior.
        
        :param err_variable: The variable name of not filled variable
        :param values: The dict of current values
        :rtype: A updated dict of 'values' variable name and values
        """

        raise NotImplementedError

    def on_validation_error(self,err_variable,values):
        """This method is called when the validation of a variable is
        not satisfated. Redefine it to adapt its behavior.
        
        :param err_variable: The variable name of not filled variable
        :param values: The dict of current values
        :rtype: A updated dict of 'values' variable name and values
        """
        raise NotImplementedError

    def build_save_to(self, variable):
        """Redefine it we want to make actions (show, print, save...) on validated variables.
        
        :param variable: the variable that we want to save
        :type variable: subclass of :py:meth:`mss.variable.Variable`
        """
        pass

    def _build(self,provide_caller):
        self.provide_caller = provide_caller
        self.depth = provide_caller.depth
        # We validate this require with values returned by provide.

        ret = self.build_values()
        self._build_validate(ret)

        self._build_save_variables()

    def _build_validate(self,values):
        while True:
            try:
                if values == None:
                    values = {}
                self.fill(values)
                self.validate()
            except RequireNotFilled as e:
                values = self.on_require_not_filled_error(e.variable_name,values)
                continue
            except ValidationError as e:
                values = self.on_validation_error(e.variable_name,values)
                continue
            break


    def _build_save_variables(self):
        for v in self.variables:
            self.build_save_to(v)
        
class RequireWithProvide(Require):
    """This class is a subclass of :class:`Require` and can be use if
    the require needs to call a provide. See :class:`Require` for more
    common informations.

    When value of this kind of require are built, first a provide
    object is built and called. Then, value from this provide can be
    used to fill this require.

    DOC TODO :To build value of this require, several object are available
    """

    def build_provide_class(self):
        """Must be redefined. It must return the class that has to be
        used to build the provide needed by this require.

        :rtype: class that inherit from Provide """
        NotImplementedError

    def _provide_call(self):
        self.provide = self.build_provide_class()(lf_name = self.lf_name,
                               provide_name = self.provide_name,
                               caller_provide = self.provide_caller,
                               suggested_args = self.provide_args,
                               depth = self.depth+1)
        # Maybe, we don't want to call the proposed require. Moreover,
        # we have to choose the provide host.
        self.provide.call()

    def _build(self,provide_caller):
        self.provide_caller = provide_caller
        self.depth = provide_caller.depth

        # We call the provide to get its return values
        self._provide_call()

        # We validate this require with values returned by provide.
        ret = self.build_values()
        self._build_validate(ret)

        self._build_save_variables()
    
    def _build_save_variables(self):
        """Take a list as input and append a tuple of variable_name
        and value to this list.
        
        :param variables: a list a 2-uple variable_name and value
        """
        for v in self.variables[0]:
            self.build_save_to(v)


################################################################################
#                            HELPERS                                           #
################################################################################

def user_input_confirm(msg, prefix=''):
    """Ask the user if he confirm the msg question.

    :rtype: True if user confirm, False if not"""
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



