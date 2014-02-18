"""This module consists of several bases classes which can be used to
build a client that will automatically satisfate all requires of the
called provide.

Basicaly, you have to implement the class :py:class:`Provide` and
classes :py:class:`RequireSmart`. The class :py:class:`Provide` permits to
define how and where a provide is called. Classes :py:class:`RequireSmart`
and :py:class:`RequireWithProvide` permits to define how require
values are built.

How it works on a example::

1. User wants to call a provide. \
   For instance, Wordpress//get_website;
2. This provide xpath matches several provides. \
   Suppose the user chooses Wordpress/Active/get_website;
3. The user confirm the call to this provide;
4. The provide Wordpress/Active/get_website requires \
   a call to Mysql.addDatabase provide

   a. The user confirms if he really wants Mysql.addDatabase.
      If he doesn't, we continue to the next Require \
      of Wordpress/Active/get_site
   b. We fill Requires of Mysql.addDatabase with (in order).\
      See in :py:class:`RequireSmart` for more informations \
      about how to fill a require.

5. Once all requires have been treated, the user confirms the \
   call to the provide Wordpress/Active/get_website with the \
   filled requires.

6. Finally, the provide /Wordpress/Active/get_website is called.
"""

from mss.common import ValidationError
from mss.client.socket import ClientSocket
import mss.lifecycle 

import types

import logging
logger = logging.getLogger()

###############################################################################
#                                  REQUIRE CLASSES                            #
###############################################################################

import mss.require


class RequireSmart(object):
    """This class has to be used to handle how a require is built.  For
    external or local requires, this class is specialized in
    :py:class:`RequireWithProvide`.

    So, basically we have to handle :

    * how values of a require are built \
    (see :py:meth:`RequireSmart.build_values`)
    * what happen if a variable is not validated \
    (see :py:meth:`RequireSmart.on_validation_error`)
    * how values used to fill this require are saved \
    (see :py:meth:`RequireSmart.build_save_to`)

    To fill this require, several helpers can be used:

    * :py:meth:`helper_needed_values` permits to get the dict of \
    variable names (and their default values)
    * :py:meth:`helper_suggested_values` permits to get values \
    suggested by the requirer.

    Sometimes, a require can be called several times. This is handle
    by the method :py:meth:`handle_many_requires`. If this method
    return True, then, the require will be filled one time more.

    How from_xpath variable parameter is managed.  All variable are
    stored in class variable Provide._Variable.  When a variable has a
    from_xpath atrtibute not equal to None, the value of this xpath is
    retreived from this list and the value of the variable is set to
    the previoulsly used value.

    """

    def build_values(self):
        """Redefine it to build the value that has been used by this requires.

        :rtype: A dict of variable name and values.
        """
        raise NotImplementedError(
            "%s.build_values must be implemented" % self.__class__.__name__)

    def handle_validation_error(self):
        """Redefine it if you don't want to validate values. This can ben
        useful to run some kind of simulation, ie. the provide is not
        called. By default, it returns True. If it returns false, the
        validation process is not realized.

        :rtype: bool
        """
        return True

    def on_validation_error(self, err_variable_name, values):
        """This method is called when the validation of a variable is
        not satisfated. Redefine it to adapt its behavior.

        :param err_variable_name: The variable name of not filled variable
        :param values: The dict of current values
        :rtype: A updated dict of 'values' variable name and values
        """
        raise NotImplementedError(
            "You must implement %s.on_validation_error" % (
                self.__class__.__name__))

    def build_save_to(self, variable):
        """Redefine it we want to make actions (show, print, save...)
        on validated variables.

        :param variable: the variable that we want to save
        :type variable: subclass of :py:meth:`mss.variable.Variable`
        """
        logger.debug("%s.build_save_to(%s)" % (
            self.__class__.__name__,
            variable))
        pass

    def handle_many_requires(self, counter):
        """Return True if a new set of variable has to be provided."""
        return False

    def _build_one_validate(self):
        values = self._build_one()
        while self.handle_validation_error():
            try:
                self.validate_one_set(self.factory_variable(), values)
            except ValidationError as e:
                logger.debug(
                    "Variable %s has not been validated." % e.variable_name)
                values = self.on_validation_error(e.variable_name, values)
                continue
            break
        return values

    def _build_one(self):
        """
        Build one set a variables.

        :rtype: a dict of values
        """
        values = self.build_values()
        return values

    def _build_many(self):
        """Build value for many variables set.
        This manages the nargs arguments or this require.

        :rtype: a list of dict of values
        """
        require_values = []
        for v in self.variables():
            if v.from_xpath is not None:
                v.value = self.provide_caller.__class__.find_xpath(
                    v.from_xpath)

        while (self.nargs in ['?', '*']
               or len(require_values) < int(self.nargs)):
            if (require_values == [] or
                self.handle_many_requires(len(require_values))):
                pass
            else:
                break
            values = self._build_one_validate()
            require_values.append(values)

        return require_values

    def _build(self, provide_caller):
        """Build values of this require"""
        self.provide_caller = provide_caller
        self.depth = provide_caller.depth
        # We validate this require with values returned by provide.

        require_values = self._build_many()

        self._build_validate(require_values)
        self._build_save_variables()

    def _build_validate(self, values):
        if values is None:
            values = []
        self.fill(values)
        if self.handle_validation_error():
            self.validate()

    def _build_save_variables(self):
        for vs in self._variables:
            for v in vs:
                self.provide_caller.__class__._Variables.append(
                    (v.get_xpath(), v.value))
                self.build_save_to(v)

    def helper_needed_values(self):
        """
        To get all values needed by this require. The returned dict
        contains variable_name and the value is the current value or
        the default value.

        This is generally used as the base dict for require value
        building.

        :rtype: a dict of {variable_name : value}
        """
        return self.get_values()[0]

    def helper_suggested_values(self):
        """
        To get the variable value suggested by the local or external
        require that is the origin of the provide of this require.

        For instance, suppose that we have a external require::

          RequireExternal("external", xpath=/a_provide,
                          variables[VString("variable_name",default=value)])

        This require can generate a provide call.
        Suppose the provide 'a_provide' have the require::

          require=Require("this")

        Then, require.helper_suggested_value() will return::

          {'variable_name':value}

        :rtype: a dict of {variable_name : value}

        """
        suggested = {}
        #To ensure this require is not a goto state require
        if self in self.provide_caller.provide_requires:
            acc = []
            requirer = self.provide_caller
            while requirer is not None:
                tmp = (dict([(s.name, s.value)
                             for s in requirer.suggested_args
                             if s.value is not None]))
                acc.append(tmp)
                requirer = requirer.requirer
            for s in reversed(acc):
                suggested.update(s)
        return suggested


class RequireSmartWithProvide(RequireSmart):
    """This class is a subclass of :class:`RequireSmart` and can be use if
    the require needs to call a provide. See :class:`RequireSmart` for more
    common informations.

    When value of this kind of require are built, first a provide
    object is built and called. Then, value from this provide can be
    used to fill this require.

    This class inherits helper from
    :py:class:`RequireSmart`. Moreover, a other helper is defined:

    * :py:meth:`helper_current_provide_result_values` which permits to \
    get the return values of the current call.

    """
    def build_provide_class(self):
        """Can be redefined. It must return the class that has to be
        used to build the provide needed by this require.

        By default, it returns the class of the provide that has
        called this requirer.

        :rtype: class that inherit from Provide

        """
        return self.provide_caller.__class__

    def _provide_call(self):
        provide = self.build_provide_class()(xpath=self.xpath,
                                             requirer=self.provide_caller,
                                             requirer_type=self.type,
                                             suggested_args=self.provide_args,
                                             depth=self.depth + 1)
        # Maybe, we don't want to call the proposed require. Moreover,
        # we have to choose the provide host.
        provide.call()
        return provide

    def _build_one(self):
        provide = self._provide_call()
        self._provide_current = provide
        if not hasattr(self, "provides"):
            self.provides = []
        self.provides.append(provide)

        values = self.build_values()
        return values

    def helper_current_provide_result_values(self):
        """
        To get the dict of value returned by the last provide call.

        :rtype: a dict of {variable_name : value}
        """
        return self._provide_current.provide_ret


class Require(mss.require.Require, RequireSmart):
    pass


class RequireUser(mss.require.RequireUser, RequireSmart):
    pass


class RequireLocal(mss.require.RequireLocal, RequireSmartWithProvide):
    def _provide_call(self):
        provide = self.build_provide_class()(xpath=self.xpath,
                                             requirer=self.provide_caller,
                                             requirer_type=self.type,
                                             suggested_args=self.provide_args,
                                             depth=self.depth + 1,
                                             host=self.provide_caller.host)
        # Maybe, we don't want to call the proposed require. Moreover,
        # we have to choose the provide host.
        provide.call()
        return provide


class RequireExternal(mss.require.RequireExternal, RequireSmartWithProvide):
    pass


class Provide(object):
    """This class describes a Provide and permit to fill its require
    by creating instances of :class:`Require`.

    A initial Provide is created accorded to the user request. If this
    provide requires to call provides (external or local), these
    provides are created, their requires are satisfated and they are
    called. Then the initial provide is called.

    So, to call a provide, you have to define the ip address of the
    agent, and choose a absolute wpath if the given provide xpath is
    ambigous.

    To use this class, we have to:

    * specialize method :py:meth:`Provide.handle_call`,
    * specialize method :py:meth:`Provide.confirm_call`,
    * specialize method :py:meth:`Provide.handle_provide_xpath`,
    * bind specialized Require classes to require type by using the static \
    method :py:meth:`set_require_class`.

    By redefining this class, you can control the host where the
    provide (via :py:meth:`Provide.handle_call`) will be called, and
    control if the provide has to be call or not (via
    :py:meth:`Provide.confirm_call`).


    .. note:: You would NEVER have to manually create a Provide,\
    except the initial provide.

    :param xpath: A xpath that can match several provides.
    :type xpath: String
    :param host: Host where the provide has to be call
    :type host: String
    :param requirer: Provide that has called this one.
    :type requirer: Subclass of :class:`Provide`
    :param requirer_type: The type of the require that calls this provide.
    :type requirer_type: str
    :param suggested_args: Suggested args provided by the caller. This\
    corresponds to the require (that expect this provide) variables.
    :type suggested_args: List of Variable.
    :param depth: The depth in provide call tree
    :type depth: Integer

    """

    #Contain user specified require classes.
    _require_classes = {"external": RequireExternal,
                        "local": RequireLocal,
                        "simple": Require,
                        "user": RequireUser}

    # Class variable that contains all xpath and value filled for the main
    #provide.
    _Variables = []

    def __init__(self, xpath, host=None, requirer=None,
                 requirer_type=None,
                 suggested_args=[], depth=0):
        self.xpath = xpath
        # This describes the xpath that will be really called.
        # It can be set by the return value of handle_provide_xpath()
        self.used_xpath = xpath

        self.lf_name = None
        self.provide_name = None
        self.requires = None
        self.suggested_args = suggested_args
        self.host = host
        self.depth = depth
        self.requirer = requirer
        self.requirer_type = requirer_type

        # This is filled by self.call(). This contains the dict of
        # returned value by this provide.
        self.provide_ret = {}

    def handle_connection_error(self):
        """This method is called when a mss connection occurs.
        If it return True, the mss call is triyed again.
        If False, exception is raised.
        By default, it returns false."""
        return False

    def handle_provide_xpath(self, xpath, matches):
        """This method is called when the xpath doesn't match a unique
        provide. Redefine it to choose the good one.

        :param xpath: submitted xpath
        :param matches: list of xpath that match the submitted xpath
        :rtype: a xpath (str)
        """
        raise NotImplementedError(
            "Method handle_provide_xpath must be implemented!")

    def handle_call(self):
        """Redefine it to validate that the inferred provide should be called.
        Generally, the Provide.host variable of this provide is sets here.

        :rtype: Return True if the provide must be called, false otherwise
        """
        raise NotImplementedError("Method handle_call is not implemented!")

    def confirm_call(self):
        """Redefine it to confirm the provide call after that requires
        have been filled.
        By default, it returns True.
        :rtype: boolean"""
        return True

    def on_provide_call_begin(self):
        """This can be redefine to do some action just before
        the provide is called."""
        logger.debug("on_call_provide_begin()")

    def on_provide_call_end(self):
        """This can be redefine to do some action just after the provide
        has been called."""
        logger.debug("on_call_provide_end()")

    def set_logging_handlers(self):
        """Redefine it to get agent logs.

        :rtype: logging.Handler
        """
        return []

    def helper_requirer_type(self):
        """Return the type of the requirer that has called this provide."""
        return self.requirer_type

    def helper_used_xpath(self):
        """Return the xpath that is used, ie. the xpath that the user has
        choosen amongst matched xpath.

        :rtype: xpath (string)"""
        return self.used_xpath


    def _lf_manager(self):
        return ClientSocket(host=self.host,
                            handlers=self.set_logging_handlers())

    def _get_requires(self):
        logger.debug("Requires needed to call provide '%s' on '%s':" % (
            self.used_xpath,
            self.host))
        self.lf_manager = self._lf_manager()

        # We specialize the generic xpath
        matches = self.lf_manager.uri(xpath=self.used_xpath)
        # If the generic xpath matches several xpaths, 
        # the user has to choose one
        if len(matches) != 1:
            self.used_xpath = self.handle_provide_xpath(
                self.used_xpath, matches)
        else:
            self.used_xpath = matches[0]
        while True:
            try:
                self.provide_goto_requires = self.lf_manager.provide_call_requires(
                    xpath=self.used_xpath)

                self.provide_requires = self.lf_manager.provide_call_args(
                    xpath=self.used_xpath)

            except mss.client.socket.ConnectionError:
                if self.handle_connection_error():
                    continue
                else:
                    raise
            break
        self.requires = self.provide_goto_requires + self.provide_requires

    def call(self):
        if self.handle_call():
            self.on_provide_call_begin()

            #if self.host is None:
            #    raise TypeError("host can not be 'None'")
            self._build_requires()

            if self.confirm_call():
                provide_requires_primitive = self._generate_requires_primitive(
                    self.provide_goto_requires)
                provide_args_primitive = self._generate_requires_primitive(
                    self.provide_requires)
                logger.debug("mss.call(%s, %s, %s) ..." % (
                    self.used_xpath,
                    provide_requires_primitive,
                    provide_args_primitive))

                self.provide_ret = self.lf_manager.provide_call(
                    xpath=self.used_xpath,
                    requires=provide_requires_primitive,
                    provide_args=provide_args_primitive)
                self.on_provide_call_end()

                logger.debug("mss.call(%s, %s, %s) done." % (
                    self.used_xpath,
                    provide_requires_primitive,
                    provide_args_primitive))

                # Because provide return type is currently not strict.
                # This must be FIXED because useless.
                if self.provide_ret is None:
                    self.provide_ret = {}
        return self.provide_ret

    def _generate_requires_primitive(self, require_list):
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
            if r.type in self._require_classes:
                r.__class__ = self._require_classes[r.type]
                r._xml_register_children = types.MethodType(
                    _xml_register_children, r)
            r._build(self)

        for r in (requires_simple + requires_user):
            if r.type in self._require_classes:
                r.__class__ = self._require_classes[r.type]
                r._xml_register_children = types.MethodType(
                    _xml_register_children, r)
            r._build(self)

    @classmethod
    def find_xpath(cls, xpath):
        """Try to find in the Provide._Variables array
        the value associated to xpath.

        :rtype: a value, None otherwise.
        """
        for v in cls._Variables:
            if v[0].endswith(xpath):
                return v[1]
        return None

    @classmethod
    def set_require_class(cls, require_type, klass):
        """Use this method to specify which Require subclass has to be
        used for a require type.

        Once Requires classes have been specialized, they are attach
        to the specialized Provide class by calling the method.
        """
        cls._require_classes.update({require_type: klass})


# Really shitty hack!  Because _xml_elt is not forwarded via
# pickling, we have to manually create xpath in order to be able
# to save it.
#
# This method is just called when multiple variable
# are filled by a client to validate them.
def _xml_register_children(require):
    if len(require.variables(all=True)) > 1:
        for idx, vs in enumerate(require.variables(all=True)):
            for v in vs:
                xpath_relative = v.get_xpath_relative() + "[%s]" % (idx + 1)
                xpath = v.get_xpath() + "[%s]" % (idx + 1)

                v._xpath_relative = xpath_relative
                v._xpath = xpath


class LocalProvide(Provide):
    def __init__(self, xpath, requirer=None,
                 requirer_type=None,
                 suggested_args=[], depth=0):
        Provide.__init__(self, xpath, host=None, requirer=requirer,
                         requirer_type=requirer_type,
                        suggested_args=suggested_args, depth=depth)

    def _lf_manager(self):
        return mss.lifecycle.LifecycleManager()

###############################################################################
#                            HELPERS                                          #
###############################################################################

def update_empty(origin, *dcts):
    """Take a origin dict with some values equal to None. Fill these
    value with values from other dicts.

    Example:
    update_empty({'a':1,'b':None,'c':2}, {'a':4, 'b':1}, {'c':4, 'b':2})
    >> {'a': 1, 'c': 2, 'b': 1}
    """
    for (ko, vo) in origin.items():
        if vo is None:
            found = False
            for d in dcts:
                if found:
                    break
                for (k, v) in d.items():
                    if k == ko:
                        origin.update({k: v})
                        found = True
                        break
    return origin


def build_initial_provide(klass, host, xpath):
    """Build a initial provide.

    :param klass: the class of user definied Provide.
    :type klass: inherit from :py:class:`Provide`.
    :param host: the host where is located the agent.
    :param xpath: a xpath that can match several provide.
    """
    provide = klass(xpath=xpath, host=host)
    return provide
