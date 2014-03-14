"""This module is used to describe the Lifecycle of a service.

A service is represented by a kind of state machine :class:`Lifecycle`.

This state machine is composed by :class:`State` which represents differents
steps of a service managment, for instance, installation, configuration,
activation.

Class :class:`LifecycleManager` permits to manage these :class:`Lifecycle`,
for instance, load a service lifecycle, list available services...

Main concepts
-------------

Lifecycle
^^^^^^^^^^^^^^^^^^^^

:class:`Lifecycle` is an automaton with a set of :class:`State` and
transitions between these states. See :class:`Lifecycle` for more
informations.

State
^^^^^^^^^^^^^^^^^^^^

A state describes actions on a service. For instance, a state can
describe packages installation, or configuration, etc. See
:class:`State` for more informations.

MetaState
^^^^^^^^^^^^^^^^^^^^

A :class:`MetaState` permits to simplify transitions writing. For instance, if
you have a state ActiveOnDebian and ActiveOnMBS, you can create a
metastate Active which has ActiveOnMBS and ActiveOnDebian as
'implementations'. It is then sufficient to specify Active in
lifecycle transitions because all metastate implementations are
automatically added as intermediate state. See
:class:`armonic.modules.mysql.Mysql` for an example.

Note: We don't use python inheritance in order to avoid provide
replication in all metastate implementations.


Stack
^^^^^^^^^^^^^^^^^^^^

When a state is reached, it is push on a stack managed by
:class:`Lifecycle`. This permits to know which states have been
applied in order to be able to pop them. This stack in internally
managed and then not exposed.

Requires
^^^^^^^^^^^^^^^^^^^^

Parameters needed to reach a state are called *requires*.
*Requires* of a state are specified in the list :py:attr:`State.requires`.
Different kinds of *requires* are predefined.

A state can express different types of requires. For instance, the
Wordpress module needs a vhost provided by apache. This require is
then a local require and module wordpress specify that this require
can be provided by the provide get_vhost of module apache. Wordpress
also needs a database which can be provided by provide get_db of mysql
module on another machine.

For more informations, see

* :py:attr:`State.requires`
* :class:`Require`
* :class:`RequireExternal`
* :class:`RequireLocal`

Provides
^^^^^^^^^^^^^^^^^^^^

A state can expose methods to interact with this state or just get
some informations about this state. These methods are called
'provides'. To call a provide, the state which exposes this provides
must be in the stack or this state will be reached (not yet
implemented). To define a state method as a *provide*, this method
must be decorated with :py:func:`provide`. See :py:func:`provide` for
more informations.

Provide Flags
^^^^^^^^^^^^^^^^^^^^

When a provides is called, the state that provides it is in the
stack. At each provide, some 'flags' can be attached. From these state
to top of stack, method :py:meth:`State.cross` of each state is called
with flags defined by the provide. For instance, if a provide that
change something in the Configuration State is defined and this
service needs to be restarted, this provide can define a 'restart'
flags and the method :py:meth:`State.cross` of Active state can
restart the service when this method is called with a 'restart' flags.

Motivations of flags: For instance, when a vhost is added to Httpd
module, apache service must be reloaded. If the current state is
Active, and if we want to add a vhost, we don't want to stop Apache
(ie. leave Active state), goto to configuration state, and go back to
active state. We want to reload the services. This is done via cross
method of Httpd active state.


"""

import inspect
import logging
import pprint
import os
import copy
import sys

from armonic.common import IterContainer, DoesNotExist, ProvideError, format_input_variables
from armonic.provide import Provide
from armonic.variable import ValidationError
import armonic.utils

from xml_register import XmlRegister, Element, SubElement

logger = logging.getLogger(__name__)
STATE_RESERVED_METHODS = ('enter', 'leave', 'cross')
STATE_RESERVED_PROVIDES = ('enter',)


class TransitionNotAllowed(Exception):
    pass


def Transition(s, d):
    return (s, d,)


class ProvideNotExist(Exception):
    pass


class ProvideNotInStack(Exception):
    pass


class ProvideAmbigous(Exception):
    pass


class RequireHasNotFuncArgs(Exception):
    pass


class StateNotApply(Exception):
    pass


class StateNotExist(Exception):
    pass


class State(XmlRegister):
    """A State describes a step during the life of a :class:`Lifecycle`.

    Each State can have some Requires. :class:`Require` objects
    defines the arguments required to enter the State.

    To define a new State, it is necessary to redefine methods:
     :py:meth:`State.enter`
     :py:meth:`State.leave`
     :py:meth:`State.cross`
    """
    _lf_name = ""
    _instance = None
    supported_os_type = [armonic.utils.OsTypeAll()]

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            # init provides
            cls._provides = IterContainer()

            # setup reserved provides
            for method_name in STATE_RESERVED_PROVIDES:
                method = getattr(cls, method_name).__func__
                if not hasattr(method, "_provide"):
                    setattr(method, "_provide", Provide(method_name))
                # setup class properties to access reserved provides
                # cls.provide_enter etc...
                setattr(cls, "provide_%s" % method_name, property(lambda self: getattr(method, "_provide")))

            # register custom provides
            funcs = inspect.getmembers(cls, predicate=inspect.ismethod)
            for (fname, f) in funcs:
                if hasattr(f, '_provide') and fname not in STATE_RESERVED_METHODS:
                    cls._provides.append(f._provide)
                    logger.debug("Registered %s in %s" % (f._provide, cls._instance))

            cls._instance = super(State, cls).__new__(cls, *args, **kwargs)

        return cls._instance

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        provides = []
        for method_name in STATE_RESERVED_PROVIDES:
            provides.append(getattr(self, "provide_%s" % method_name))
        return provides + self.provides

    def _xml_ressource_name(self):
        return "state"

    def _xml_add_properties(self):
        acc = []
        for s in self.supported_os_type:
            t = Element("supported_os")
            name = SubElement(t, "name")
            name.text = s.name
            r = SubElement(t, "release")
            r.text = s.release
            acc.append(t)
        return acc

    @property
    def name(self):
        """Name of the state"""
        return self.__class__.__name__

    @property
    def lf_name(self):
        """Shity hack. This return the name of the lifecycle using this
        state. It is set by :py:meth:`Lifecycle._push_state` method.
        """
        return self._lf_name

    @lf_name.setter
    def lf_name(self, name):
        self._lf_name = name

    def safe_enter(self, requires=[]):
        """Check all state requires are satisfated and enter into State

        :param requires: A list of of tuples (variable_xpath, variable_values)
            variable_xpath is a full xpath
            variable_values is dict of index=value
        :type requires: list
        """
        self.provide_enter.fill(requires)
        self.provide_enter.validate()
        try:
            if self.provide_enter:
                return self.enter(self.provide_enter)
            else:
                return self.enter()
        except ValidationError:
            raise
        except Exception, e:
            raise ProvideError(self.provide_by_name('enter'), e.message, sys.exc_info())

    def enter(self):
        """Called when a state is applied"""
        logger.debug("Entering state %s" % self.name)

    def leave(self):
        """Called when a state is leaved"""
        logger.debug("Leaving state %s" % self.name)

    def cross(self, **kwargs):
        """Called when the state is traversed"""
        logger.info("State %s crossed but nothing to do" % self.name)

    def enter_doc(self):
        """NOT YET IMPLEMENTED.
        By default, it returns doc string of enter method. You can
        override it to be more concise.

        TODO Need state to be built by LF in order to have an instance.
        """
        return self.enter.__doc__

    @property
    def provides(self):
        """
        Requires for all provides

        :rtype: IterContainer([:py:class:`Provide`])
        """
        return self._provides

    def provide_by_name(self, provide_name):
        """
        :param provide_name: name of a provide
        :rtype: Provide
        """
        # Small hack for LifecycleManager.from_xpath
        if provide_name in STATE_RESERVED_PROVIDES:
            return getattr(self, 'provide_%s' % provide_name)

        try:
            return self.provides.get(provide_name)
        except DoesNotExist:
            raise ProvideNotExist("%s doesn't exist in state %s" %
                                  (provide_name, self))

    def __repr__(self):
        return "<State:%s>" % self.name

    def clear(self):
        """Init variables to default values in all requires"""
        for p in self.provides:
            for r in p:
                r._init_variables()
        for r in self.provide_enter:
            r._init_variables()

    def to_primitive(self):
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "supported_os_type": [t.to_primitive() for t in
                                      self.supported_os_type],
                "provides": [r.to_primitive() for r in self.provides],
                "provide_enter": self.provide_enter.to_primitive()}


class MetaState(State):
    """Set by state.__new__ to add implementation of this metastate."""
    implementations = []


class Lifecycle(XmlRegister):
    """The Lifecycle of a service or application is represented
    by transitions between :class:`State` classes.
    The transitions list is specified in the class attribute
    :attr:`Lifecycle.transition`.

    Main operations on a Lifecycle are:

    * :meth:`Lifecycle.state_list` to list available states,
    * :meth:`Lifecycle.state_current` to know the current state,
    * :meth:`Lifecycle.state_goto` to go from current state to another state.
    * :meth:`Lifecycle.provide_call` to call a provide.

    States applied are recorded in a stack to be able to unapply them.
    The State stack does not contain the same State twice.
    """
    _initialized = False

    os_type = armonic.utils.OS_TYPE
    """To specify the current OS type. By default, OS type is
    automatically discovered but it is possible to override this
    attribute to manually specify one.
    """
    abstract = False
    """If the Lifecycle is abstract it won't be loaded in the LifecycleManager
    and in the XML registery.
    """
    initial_state = None
    """The initial state for this Lifecycle"""

    def __new__(cls):
        instance = super(Lifecycle, cls).__new__(cls)
        # Update transitions to manage MetaState
        for ms in instance._state_list():
            # For each MetaState ms
            if isinstance(ms, MetaState):
                # Find transitions which involve a MetaState
                # Ignore already done MetaState transitions
                transitions = [(s, i) for (s, i) in
                               instance.transitions if i == ms and not "%s." % i.name in s.name]
                if not transitions:
                    continue
                # We create new state suffixed by metaclass name This
                # permits to create specical path.  If two metastate
                # has same implementation, we need to create special
                # implementations for each metastate.
                created_states = [type('%s.%s' % (ms.__class__.__name__, s.__name__), (s,), {})
                                  for s in ms.implementations]
                for s in created_states:
                    logger.debug("State %s has been created from MetaState %s" % (s.__name__, ms.name))
                # For each transtion to MetaState ms
                for t in transitions:
                    update_transitions = []
                    # And for each state implementations
                    for d in created_states:
                        # We create transition to this implementation
                        update_transitions += [(t[0], d())]
                        # And from this implementation to metastate
                        update_transitions += [(d(), ms)]
                    # Finally, we remove useless transitions and add new ones.
                    if update_transitions != []:
                        instance.transitions.remove(t)
                        instance.transitions += update_transitions

        return instance

    def __init__(self):
        if self.initial_state:
            self.init(self.initial_state)

    def init(self, state, requires=[]):
        """If it is not already initialized, push state in stack."""
        self._stack = []
        requires = format_input_variables(requires)
        if not self._initialized:
            self._push_state(state, requires)
            self._initialized = True

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        return self.state_list()

    def _xml_ressource_name(self):
        return "lifecycle"

    def _xml_add_properties(self):
        transitions = []
        for (s, d) in self.transitions:
            t = Element("transition")
            src = SubElement(t, "source")
            src.text = s.name
            dst = SubElement(t, "destination")
            dst.text = d.name
            transitions.append(t)
        return transitions

    @property
    def name(self):
        return self.__class__.__name__

    @classmethod
    def _state_list(cls):
        return list(set([s for (s, d) in cls.transitions] + [d for (s, d) in cls.transitions]))

    def state_list(self, reachable=False):
        """To get all available states.

        :param reachable: list only reachable states from the current state
        :type reachable: bool

        :rtype: [:class:`State`]
        """
        states = self.__class__._state_list()
        if reachable:
            acc = []
            for s in states:
                if (self._get_from_state_paths(self.state_current(), s) != [] or
                        s == self.state_current()):
                    acc.append(s)
            states = acc
        return states

    def state_current(self):
        """Get current state.

        :rtype: :class:`State`
        """
        if self._stack == []:
            return None
        else:
            return self._stack[-1]

    def _is_state_in_stack(self, state):
        return self._get_state_class(state) in self._stack

    def _is_transition_allowed(self, s, d):
        """A transition is allowed if src and dst state support current os
        type."""
        return (self.os_type in d.supported_os_type
                and self.os_type in s.supported_os_type
                and (s, d) in self.transitions)

    def _push_state(self, state, requires):
        """Go to a state if transition from current state to state is allowed
        TODO: verify that state is not in stack yet.
        You should never use this method. Use goto_state instead.
        """
        if self._stack != []:
            if not self._is_transition_allowed(self.state_current(), state):
                raise TransitionNotAllowed("from %s to %s" % (self.state_current(), state))
        state.lf_name = self.name
        logger.event({'event': 'state_appling',
                      'state': state.name,
                      'lifecycle': self.name})
        ret = state.safe_enter(requires)
        self._stack.append(state)
        logger.event({'event': 'state_applied',
                      'state': state.name,
                      'lifecycle': self.name})
        logger.debug("push state '%s'" % state.get_xpath())
        return ret

    def _pop_state(self):
        if self._stack != []:
            t = self._stack.pop()
            t.leave()

    def _get_from_state_paths(self, from_state, to_state):
        logger.debug("Find paths from %s to %s" % (from_state, to_state))
        paths = []

        def _find_next_state(state, paths, path=[]):
            for (src, dst) in self.transitions:
                if src == state and self._is_transition_allowed(src, dst):
                    new_path = copy.copy(path)
                    new_path.append((dst, 'enter'))
                    paths.append(new_path)
                    if not dst == to_state:
                        _find_next_state(dst, paths, new_path)
            # we can't go further
            # should we keep this path ?
            if path and not (path[0] == from_state and path[-1] == to_state):
                # seems not! delete it
                for i, p in enumerate(paths):
                    if p == path:
                        del paths[i]

        # Check if we are going back in the stack
        # take the same path we took to go to to_state to go back to from_state
        if to_state in self._stack and from_state == self.state_current():
            logger.debug("Using same path to go back to state %s" % to_state)
            rewind_path = []
            for state in reversed(self._stack[:]):
                if state == to_state:
                    break
                else:
                    rewind_path.append((state, "leave"))
            paths.append(rewind_path)
        # trying to find a path from "to_state" to "from_state"
        # meaning we are going forward in the state machine
        else:
            _find_next_state(from_state, paths)

        logger.debug("Found paths:\n%s" % pprint.pformat(paths))
        return paths

    def _get_state_class(self, state):
        """From a string state name or a state class, try to find the state
        object.

        :rtype: the corresponding state class
        If state is not found, raise StateNotExist.
        """
        if isinstance(state, type) and issubclass(state, State):
            state = state.__name__
        elif isinstance(state, basestring):
            pass
        elif isinstance(state, State):
            state = state.name
        else:
            raise AttributeError("state must be a subclass of State or a string")
        for s in self.state_list():
            if s.name == state:
                return s
        raise StateNotExist("%s is not a valid state" % state)

    def state_by_name(self, name):
        """Get state from its name

        :param name: the name of a state
        :type name: str

        :rtype: :class:`State`
        """
        for state in self.state_list():
            if state.name == name:
                return state
        raise DoesNotExist("State %s doesn't exists" % name)

    def state_goto(self, state, requires=[], path_idx=0):
        """Go to state.

        :param state: the target state
        :type state: state_name | :class:`State`
        :param requires: variable values to fill the requires ::

            ("//xpath/to/variable", {0: value}),
            ("//xpath/to/variable", {0: value})

        :type requires: list of tuples
        :param path_idx: the path to use when there is multiple paths
            to go to the target State
        :type path_idx: int

        :rtype: None
        """
        requires = format_input_variables(requires)
        logger.debug("Goto state %s using path %i" % (state, path_idx))
        path = self.state_goto_path(state, path_idx=path_idx)
        for (state, method) in path:
            if method == "enter":
                self._push_state(state, requires)
            elif method == "leave":
                if self.state_current() == state:
                    self._pop_state()
                else:
                    raise StateNotApply(self.state_current())

    def state_goto_path_list(self, state):
        """Get the list of paths to go to State.

        :param state: the target state
        :type state: state_name | :class:`State`

        :rtype: [[(:class:`State`, method), (:class:`State`, method), ...], ...]
        """
        state = self._get_state_class(state)
        logger.debug("Get paths to go to state %s" % state)
        return self._get_from_state_paths(self.state_current(), state)

    def state_goto_path(self, state, func=None, path_idx=0):
        """Get one path to go to State.

        :param state: the target state
        :type state: state_name | :class:`State`
        :param func:  function to apply on all States of the path
        :type func: function
        :param path_idx: the path to use when there is multiple paths
            to go to the target State
        :type path_idx: int

        :rtype: [(:class:`State`, method), (:class:`State`, method), ...]
        """
        try:
            path = self.state_goto_path_list(state)[path_idx]
        except IndexError:
            raise StateNotApply()
        if func is not None:
            for state, method in path:
                func(state)
        return path

    def state_goto_requires(self, state, path_idx=0):
        """Get Requires to go to State.

        :param state: the target state
        :type state: state_name | :class:`State`
        :param path_idx: the path to use when there is multiple paths
            to go to the target State
        :type path_idx: int

        :rtype: [:class:`Provide`]
        """
        acc = IterContainer()
        for state, method in self.state_goto_path(state, path_idx=path_idx):
            if method == "enter":
                if state.provide_enter:
                    acc.append(state.provide_enter)
        return acc

    def provide_list(self, reachable=False):
        """Get all available provides

        :param reachable: list only reachable provides from the current state
        :type reachable: bool

        :rtype: [(:class:`State`, [:class:`Provide`])]
        """
        return [(s, s.provides) for s in self.state_list(reachable=reachable)
                if s.provides != []]

    def provide_call_requires(self, state, path_idx=0):
        """Get requires to call provide in state.

        :param state: the target state
        :type state: state_name | :class:`State`
        :param path_idx: the path to use when there is multiple paths
            to go to the target State
        :type path_idx: int
        """
        state = self._get_state_class(state)
        if not self._is_state_in_stack(state):
            return self.state_goto_requires(state, path_idx)
        else:
            return []

    def provide_call_args(self, state_name, provide_name):
        """From a provide_name, returns its needed arguments."""
        state = self._get_state_class(state_name)
        return state.provide_by_name(provide_name)

    def provide_call_path(self, state):
        """Get paths to call a provide in state.

        :param state: the target state
        :type state: state_name | :class:`State`
        """
        state = self._get_state_class(state)
        if not self._is_state_in_stack(state):
            return self.state_goto_path_list(state)
        else:
            return []

    def provide_call(self, state, provide_name, requires=[], path_idx=0):
        """Go to provide state and call provide.

        :param state: the target state
        :type state: state_name | :class:`State`
        :param provide_name: name of the provide
        :type provide_name: str
        :param requires: variable values to fill the requires ::

            ("//xpath/to/variable", {0: value}),
            ("//xpath/to/variable", {0: value})

        :type requires: list of tuples

        :rtype: provide result
        """
        requires = format_input_variables(requires)
        state = self._get_state_class(state)
        # To be sure that the provide exists
        state.provide_by_name(provide_name)
        if not self._is_state_in_stack(state):
            self.state_goto(state, requires, path_idx)
        return self._provide_call_in_stack(state, provide_name, requires)

    def _provide_call_in_stack(self, state, provide_name, requires=[]):
        """Call a provide by name. State which provides must be in the stack."""
        state = self._get_state_class(state)
        state_index = self._stack.index(state)
        provide = state.provide_by_name(provide_name)
        provide_method = getattr(state, provide_name)
        provide.fill(requires)
        provide.validate()
        try:
            if provide:
                ret = provide_method(provide)
            else:
                ret = provide_method()
        except ValidationError:
            raise
        except Exception, e:
            raise ProvideError(provide, e.message, sys.exc_info())
        logger.debug("Provide %s returns values %s" % (provide_name, ret))
        if not state == self.state_current():
            logger.debug("Propagate flags %s to upper states" % provide.flags)
            for s in self._stack[state_index:]:
                s.cross(**(provide.flags))
        return ret

    def to_dot(self, cross=False,
               enter_doc=False,
               leave_doc=False,
               reachable=False):
        """Return a dot string of lifecycle."""

        def dotify(string):  # To remove illegal character
            if string is not None:
                tmp = string.replace("{", "").replace("}", "").replace(":", "").replace("\n", "\l")
                tmp += '\l'
                return tmp
            else:
                return string

        def list_to_table(l):
            if l == []:
                acc = ""
            else:
                acc = dotify(str(l[0]))
                if len(l) > 1:
                    for a in l[1:]:
                        acc += "| %s" % dotify(str(a))
            return acc

        def dot_provide(provide):
            if provide != []:
                return "%s | {%s}" % (
                    dotify(provide.name),
                    list_to_table([r.name for r in provide]))
            else:
                return ""

        acc = ""
        acc += "digraph finite_state_machine {\n"
        acc += "node [shape = ellipse];\n"
        state_list = self.state_list(reachable=reachable)
        for s in state_list:
            acc += '"%s"[\n' % s.name
            acc += 'shape = "record"\n'
            #requires = ""
            #provides = list_to_table([(p.name, p.flags) for p in
                                      #s.provides])
            # Begin of label
            acc += 'label = "{%s | %s ' % (
                s.name,
                dotify(s.__doc__),
            )
            # Enter doc
            if enter_doc:
                acc += " | Entry: %s" % (dotify(s.enter.__doc__))
            if leave_doc:
                acc += " | Leave: %s" % (dotify(s.leave.__doc__))
            # Cross method
            if cross:
                acc += "| {Cross: | {Doc: %s | Flags: %s}}" % (
                    dotify(s.cross.__doc__),
                    inspect.getargspec(s.cross).args[1:])
            # Enter Requires
            acc += "| { enter\l | {%s}}" % list_to_table([r.name for r in
                                                          s.provide_enter])
            for p in s.get_provides():
                acc += " | { %s }" % dot_provide(p)
            # End of label
            acc += '}"\n'
            acc += "];\n"
        for (s, d) in self.transitions:
            if s in state_list and d in state_list:
                acc += '"%s" -> "%s";\n' % (s.name, d.name)
        acc += "}\n"
        return acc

    def __repr__(self):
        return "<Lifecycle:%s>" % self.name

    def clear(self):
        """Init variables to default values in all requires of all states"""
        for s in self.state_list():
            s.clear()

    def to_primitive(self, reachable=False):
        state_list = self.state_list(reachable=reachable)
        return {'name': self.name,
                'xpath': self.get_xpath_relative(),
                'states': [s.to_primitive() for s in state_list],
                "transitions": [(s.name, d.name) for (s, d) in
                                self.transitions if s in
                                state_list and d in state_list]}


class LifecycleNotExist(Exception):
    pass


class LifecycleManager(object):
    """The :class:`LifecyleManager` is used to manage :py:class:`Lifecyle`
    objects. It permits to interact with lifecycles by provinding xpaths.

    The full path to a variable is::

        /hostname/lifecycle_name/state_name/provide_name/require_name/variable_name

    The xpath to get all states of the Mysql :class:`Lifecyle` would be::

        //Mysql/*

    To get the ``add_database`` provide in the Mysql :class:`Lifecyle`::

        //Mysql//add_database

    All methods of :py:class:`LifecyleManager` returns python objects.

    :param modules_dir: the path of the modules root directory
    :param include_modules: the list of wanted modules
    :param os_type: to specify which kind of os has to be used.
        If it is not specified, the os type is automatically discovered.
    """
    def __init__(self, modules_dir=None, include_modules=None, os_type=None, autoload=True):
        # empty the XML register before proceeding
        XmlRegister.clear()

        if modules_dir is not None:
            armonic.common.load_lifecycles(os.path.abspath(modules_dir),
                                       include_modules=include_modules)

        self.os_type = os_type
        self.lf_loaded = {}
        self.lf = {}
        for lf in armonic.utils.get_subclasses(Lifecycle):
            if not lf.abstract:
                logger.debug("Found Lifecycle %s" % lf)
                self.lf.update({lf.__name__: lf})
                if autoload:
                    self.load(lf.__name__)
            else:
                logger.debug("Ignoring abstract Lifecycle %s" % lf)

    def info(self):
        """Get info of armonic agent

        :rtype: dict
        """
        return {"os-type": armonic.utils.OS_TYPE.name,
                "os-release": armonic.utils.OS_TYPE.release}

    def lifecycle(self, lifecycle_xpath):
        """List loaded lifecycle objects

        :param lifecycle_xpath: xpath that matches lifecycles
        :type lifecycle_xpath: str

        :return: list of :class:`Lifecycle`
        :rtype: [:class:`Lifecycle`]
        """
        elts = XmlRegister.find_all_elts(lifecycle_xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            lf = self.lifecycle_by_name(lf_name)
            acc.append(lf)
        return acc

    def load(self, lf_name):
        """Load a :class:`Lifecycle` in the manager and register it in the
        XML register.

        :param lf_name: the :class:`Lifecycle` name to load
        :type lf_name: str

        :raises LifecycleNotExist: if the :class:`Lifecycle` isn't found
        :return: the loaded :class:`Lifecycle`
        :rtype: :class:`Lifecycle`
        """
        try:
            lf = self.lf[lf_name]()
            # Reset variables values in all States
            # since States are Singleton
            lf.clear()
            if self.os_type is not None:
                lf.os_type = self.os_type
            lf._xml_register()
        except KeyError:
            raise LifecycleNotExist("Lifecycle '%s' doesn't exist" % lf_name)
        self.lf_loaded.update({lf_name: lf})
        return lf

    def lifecycle_by_name(self, lf_name):
        try:
            self.lf_loaded[lf_name]
        except KeyError:
            self.load(lf_name)
        try:
            return self.lf_loaded[lf_name]
        except KeyError:
            raise LifecycleNotExist("%s is not loaded" % lf_name)

    def state(self, state_xpath):
        """Return a list of states that matches state_xpath.

        :param state_xpath: xpath that can match multiple states
        :type state_xpath: str

        :return: list of :class:`State`
        :rtype: [:py:class:`State`]
        """
        elts = XmlRegister.find_all_elts(state_xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            state_name = XmlRegister.get_ressource(e, "state")
            state = self.lifecycle_by_name(lf_name)._get_state_class(state_name)
            acc.append(state)
        return acc

    def state_current(self, lifecycle_xpath):
        """Get the current state name of matched lifecycles.

        :param lifecyle_xpath: xpath that can match multiple :class:`Lifecycle`

        :rtype: [:class:`State`]
        """
        # TODO return (Lifecycle, State)
        elts = XmlRegister.find_all_elts(lifecycle_xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            lf = self.lifecycle_by_name(lf_name)
            acc.append(lf.state_current())
        return acc

    def state_goto_path(self, state_xpath):
        """From the current state, returns all paths to goto states that
        match state_xpath.

        :param state_xpath: xpath that can match multiple states
        :type state_xpath: str

        :return: list of paths for every state matched by state_xpath
        :rtype: [(:class:`State`, [path])]
        """
        elts = XmlRegister.find_all_elts(state_xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            state_name = XmlRegister.get_ressource(e, "state")
            state = self.lifecycle_by_name(lf_name)._get_state_class(state_name)
            paths = self.lifecycle_by_name(lf_name).state_goto_path_list(state_name)
            acc.append((state, paths))
        return acc

    def state_goto_requires(self, state_xpath_uri, path_idx=0):
        """Return the list a special provide required to go from the current
        state to the state that match state_xpath_uri.

        :param state_xpath_uri: unique state xpath
        :type state_xpath_uri: str
        :param path_idx: path to use when there is multiple paths
            to go to the provide
        :type path_idx: int

        :rtype: [:py:class:`Provide`]
        """
        lf_name = XmlRegister.get_ressource(state_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(state_xpath_uri, "state")
        lf = self.lifecycle_by_name(lf_name)
        return lf.state_goto_requires(state_name)

    def state_goto(self, state_xpath_uri, requires=[], path_idx=0):
        """From the current state go to state.

        :param xpath: unique xpath of a state
        :type xpath: str
        :param requires: list of of tuples (variable_xpath, variable_values):
            variable_xpath is a full xpath
            variable_values is dict of index=value
        :type requires: list

        :rtype: None
        """
        requires = format_input_variables(requires)
        lf_name = XmlRegister.get_ressource(state_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(state_xpath_uri, "state")
        logger.debug("state-goto %s %s %s" % (
                     lf_name, state_name, requires))
        return self.lifecycle_by_name(lf_name).state_goto(state_name, requires)

    def provide(self, provide_xpath):
        """Provides that match provide_xpath.

        :param provide_xpath: xpath to provide
        :type provide_xpath: str

        :return: list of provides that match provide_xpath
        :rtype: [:py:class:`Provide`]
        """
        matches = armonic.xml_register.XmlRegister.find_all_elts(provide_xpath)
        acc = IterContainer()
        for m in matches:
            if XmlRegister.is_ressource(m, "provide"):
                provide_name = XmlRegister.get_ressource(m, "provide")
                if provide_name not in STATE_RESERVED_METHODS:
                    lf_name = XmlRegister.get_ressource(m, "lifecycle")
                    state_name = XmlRegister.get_ressource(m, "state")
                    state = self.lifecycle_by_name(lf_name).state_by_name(state_name)
                    acc.append(state.provide_by_name(provide_name))
        return acc

    def provide_call_requires(self, provide_xpath_uri, path_idx=0):
        """Requires for the provide.

        :param provide_xpath_uri: unique xpath to provide
        :type provide_xpath_uri: str
        :param path_idx: path to use when there is multiple paths
            to go to the provide
        :type path_idx: int

        :return: list of provides to call it order to call provide_xpath_uri
        :rtype: [:py:class:`Provide`]
        """
        lf_name = XmlRegister.get_ressource(provide_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(provide_xpath_uri, "state")
        return self.lifecycle_by_name(lf_name).provide_call_requires(state_name, path_idx)

    def provide_call_path(self, provide_xpath):
        """Paths for provides that matches provide_xpath.

        :param provide_xpath: xpath to provide
        :type provide_xpath: str

        :return: list of paths to call provides that match provide_xpath
        :rtype: [(:py:class:`Provide`, [path, ...])]
        """
        matches = armonic.xml_register.XmlRegister.find_all_elts(provide_xpath)
        acc = []
        for m in matches:
            if XmlRegister.is_ressource(m, "provide"):
                provide_name = XmlRegister.get_ressource(m, "provide")
                if provide_name not in STATE_RESERVED_METHODS:
                    lf_name = XmlRegister.get_ressource(m, "lifecycle")
                    lf = self.lifecycle_by_name(lf_name)
                    state_name = XmlRegister.get_ressource(m, "state")
                    state = lf.state_by_name(state_name)
                    provide = state.provide_by_name(provide_name)
                    acc.append((provide, lf.provide_call_path(state_name)))
        return acc

    def provide_call_validate(self, provide_xpath_uri, requires=[], path_idx=0):
        """Validate requires to call the provide

        :param xpath: unique xpath of the provide to call
        :type xpath: str
        :param requires: list of of tuples (variable_xpath, variable_values)::

            ("//xpath/to/variable", {0: value}),
            ("//xpath/to/variable", {0: value})

        :type requires: list

        :return: list of validated provides to call in order to call provide_xpath_uri
        :rtype: {'errors': bool, 'xpath': xpath, 'requires': [:class:`Provide`]}
        """
        variables_values = format_input_variables(requires)
        logger.debug("Validating variables %s" % variables_values)
        # check that all requires are validated
        # copy requires we don't want to fill variables yet
        requires = copy.deepcopy(self.provide_call_requires(provide_xpath_uri))
        try:
            requires.append(copy.deepcopy(self.from_xpath(provide_xpath_uri, "provide")))
        except DoesNotExist:
            pass
        errors = False
        for provide in requires:
            try:
                provide.fill(variables_values)
                provide.validate()
            except ValidationError:
                errors = True
        return {'xpath': provide_xpath_uri, 'errors': errors, 'requires': requires}

    def provide_call(self, provide_xpath_uri, requires=[], path_idx=0):
        """Call a provide of a lifecycle and go to provider state if needed

        :param xpath: xpath of the provide to call
        :type xpath: str
        :param requires: list of of tuples (variable_xpath, variable_values):
            variable_xpath is a full xpath
            variable_values is dict of index=value

        :return: provide_xpath_uri call result
        """
        requires = format_input_variables(requires)
        logger.debug("Provide call %s" % provide_xpath_uri)
        # be sure that the provide can be validated
        # we don't want to change states if we can't call the provide in the end
        if self.provide_call_validate(provide_xpath_uri, requires)['errors']:
            logger.error("Provided values doesn't met provide requires")
            raise ValidationError("Provided values doesn't met provide requires")
        requires = format_input_variables(requires)
        lf_name = XmlRegister.get_ressource(provide_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(provide_xpath_uri, "state")
        provide_name = XmlRegister.get_ressource(provide_xpath_uri, "provide")
        logger.debug("Calling provide %s" % provide_xpath_uri)
        return self.lifecycle_by_name(lf_name).provide_call(state_name,
                                                            provide_name,
                                                            requires,
                                                            path_idx)

    def to_dot(self, lf_name, reachable=False):
        """Return the dot string of a lifecyle object

        :param lf_name: name of the lifecycle object
        :type lf_name: str

        :rtype: dot file string"""
        return self.lifecycle_by_name(lf_name).to_dot(reachable=reachable)

    def to_primitive(self, lf_name, reachable=False):
        """Return a serialized Lifecycle object

        :param lf_name: name of the :class:`Lifecycle` object
        :type lf_name: str

        :return: serialized :class:`Lifecycle` object
        :rtype: dict"""
        return self.lifecycle_by_name(lf_name).to_primitive(reachable=reachable)

    def uri(self, xpath="//"):
        """Return the list of xpath_uris that match this xpath.

        :param xpath: an xpath string
        :type xpath: str

        :return: list of xpaths
        :rtype: [xpath_uri]"""
        return armonic.xml_register.XmlRegister.find_all_elts(xpath)

    def from_xpath(self, xpath, ret="lifecycle"):
        """From a xpath try to get the object of type ``ret``

        :param xpath: xpath to a ressource
        :type xpath: str
        :param ret: object type to return (lifecycle, state, provide, require, variable)
        :type ret: str

        :rtype: :class:`Lifecycle` | :class:`State` | :class:`Provide` | :class:`Require` | :class:`Variable`
        """
        ressource_obj = self
        ressources_types = ("lifecycle", "state", "provide", "require", "variable")
        for ressource_type in ressources_types:
            ressource_name = XmlRegister.get_ressource(xpath, ressource_type)
            ressource_obj = getattr(ressource_obj, "%s_by_name" % ressource_type)(ressource_name)
            if ressource_type == ret:
                return ressource_obj
        raise DoesNotExist("Can't find object")

    def xpath(self, xpath):
        return armonic.xml_register.XmlRegister.xpath(xpath)

    def to_xml(self, xpath=None):
        """Return the xml representation of the :class:`LifecyleManager`."""
        return armonic.xml_register.XmlRegister.to_string(xpath)