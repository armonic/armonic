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
:class:`mss.modules.mysql.Mysql` for an example.

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
import itertools

from mss.common import IterContainer, DoesNotExist
from mss.provide import Provide
from mss.variable import ValidationError
import mss.utils

from xml_register import XmlRegister, Element, SubElement

logger = logging.getLogger(__name__)
STATE_RESERVED_METHODS = ('enter', 'leave', 'cross')


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


def flags(flags):
    """Decorator to add flags to a function."""
    def wrapper(func):
        #args = inspect.getargspec(func)
        if not hasattr(func, "_requires"):
            setattr(func, "_requires", [])
        func._flags = flags
        return func
    return wrapper


def provide():
    """Decorator to say that a method is a provide"""
    # Should be improved: Each provide method should have a
    # _is_provide attr, a optionnal _flags attr and an optionnal
    # _requires attr
    return flags({})


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
    supported_os_type = [mss.utils.OsTypeAll()]

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(State, cls).__new__(cls, *args, **kwargs)

            # init requires
            cls._provides = IterContainer()
            for method in STATE_RESERVED_METHODS:
                setattr(cls, "_requires_%s" % method, Provide(method, []))

            funcs = inspect.getmembers(cls, predicate=inspect.ismethod)
            for (fname, f) in funcs:
                if hasattr(f, '_requires'):
                    if f.__name__ in STATE_RESERVED_METHODS:
                        r = Provide(f.__name__, f._requires)
                        setattr(cls, "_requires_%s" % f.__name__, r)
                    else:
                        flags = f._flags if hasattr(f, '_flags') else {}
                        r = Provide(f.__name__, f._requires, flags)
                        cls._provides.append(r)

                    logger.debug("Create a Provide for %s.%s with Require %s" % (cls.__name__, f.__name__, [t.name for t in r]))

        return cls._instance

    def _xml_tag(self):
        return self.name

    def _xml_children(self):
        acc = []
        for method in STATE_RESERVED_METHODS:
            require = getattr(self, "_requires_%s" % method)
            if require is not None:
                acc.append(require)

        return self.provides + acc

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
        self.requires_enter.fill(requires)
        self.requires_enter.validate()
        return self.enter()

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
    def requires_enter(self):
        """
        Requires to enter the state

        :rtype: :class:`Provide`
        """
        return self._requires_enter

    @property
    def requires_leave(self):
        """
        Requires to leave the state

        :rtype: :class:`Provide`
        """
        return self._requires_leave

    @property
    def requires_cross(self):
        """
        Requires to cross the state

        :rtype: :class:`Provide`
        """
        return self._requires_cross

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
        if provide_name in ('enter', 'leave', 'cross'):
            return getattr(self, 'requires_%s' % provide_name)

        try:
            return self.provides.get(provide_name)
        except DoesNotExist:
            raise ProvideNotExist("%s doesn't exist in state %s" %
                                  (provide_name, self))

    def __repr__(self):
        return "<State:%s>" % self.name

    def to_primitive(self):
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "supported_os_type": [t.to_primitive() for t in
                                      self.supported_os_type],
                "provides": [r.to_primitive() for r in self.provides],
                "requires_enter": self.requires_enter.to_primitive()}


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

    os_type = mss.utils.OS_TYPE
    """To specify the current OS type. By default, OS type is
    automatically discovered but it is possible to override this
    attribute to manually specify one.
    """
    abstract = False
    """If the Lifecycle is abstract it won't be loaded in the LifecycleManager
    and in the XML registery.
    """

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

    def init(self, state, requires={}):
        """If it is not already initialized, push state in stack."""
        self._stack = []
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
        for s in self.state_goto_path(state, path_idx=path_idx):
            if s[1] == "enter":
                r = s[0].requires_enter
                if len(r) > 0:
                    acc.append(r)
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
        state = self._get_state_class(state)
        # To be sure that the provide exists
        state.provide_by_name(provide_name)
        if not self._is_state_in_stack(state):
            self.state_goto(state, requires, path_idx)
        return self._provide_call_in_stack(state, provide_name, requires)

    def _provide_call_in_stack(self, state, provide_name, requires=[]):
        """Call a provide by name. State which provides must be in the stack."""
        state = self._get_state_class(state)
        sidx = self._stack.index(state)
        provide = state.provide_by_name(provide_name)
        sfct = state.__getattribute__(provide.name)
        provide.fill(requires)
        provide.validate()
        ret = sfct(provide)
        logger.debug("Provide %s returns values %s" % (
            provide.name, ret))
        for i in self._stack[sidx:]:
            i.cross(**(provide.flags))
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
                                                          s.requires_enter])
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
    """The :class:`LifecyleManager` is used to manage
    :py:class:`Lifecyle`. It permits to interact with lifecycles by
    provinding Xpath.  For instance, to get all state of module
    Mysql::

    lifecyleManager.state("//Mysql/*")


    All methods of :py:class:`LifecyleManager` return python object.

    :param autoload: TODO
    :param modules_dir: the path of the modules root directory
    :param include_modules: the list of wanted modules
    :param os_type: to specify which kind of os has to be used.
        If it is not specified, the os type is automatically discovered.

    """
    def __init__(self, autoload=True, modules_dir=None, include_modules=None, os_type=None):
        # empty the XML register before proceeding
        XmlRegister.clear()

        if autoload:
            if modules_dir is None:
                raise TypeError("'modules_dir' could not be None")
            mss.common.load_lifecycles(os.path.abspath(modules_dir),
                                       include_modules=include_modules)

        self.os_type = os_type

        self._autoload = autoload
        self.lf_loaded = {}
        self.lf = {}
        for lf in mss.utils.get_subclasses(Lifecycle):
            if not lf.abstract:
                logger.debug("Found Lifecycle %s" % lf)
                self.lf.update({lf.__name__: lf})
                self.load(lf.__name__)
            else:
                logger.debug("Ignoring abstract Lifecycle %s" % lf)

    def info(self):
        """Get info of mss agent

        :rtype: list of strings (lifecycle objects names)
        """
        return {"os-type": mss.utils.OS_TYPE.name,
                "os-release": mss.utils.OS_TYPE.release}

    def lifecycle(self, lifecycle_xpath):
        """List loaded lifecycle objects.

        :param lifecycle_xpath: A xpath that matches lifecycles
        :type lifecycle_xpath: str
        :rtype: [:class:`Lifecycle`]
        """
        elts = XmlRegister.find_all_elts(lifecycle_xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            lf = self.lifecycle_by_name(lf_name)
            acc.append(lf)
        return acc

    def load(self, lf_name=None):
        """Load a lifecycle object in the manager.
        If lf_name is not set, return a list of loaded LF.

        :param lf_name: the lifecycle to load
        :type lf_name: str
        :rtype: list of lifecycle objects names
        """
        if lf_name is not None:
            try:
                lf = self.lf[lf_name]()
                if self.os_type is not None:
                    lf.os_type = self.os_type
                lf._xml_register()
            except KeyError:
                raise LifecycleNotExist("Lifecycle '%s' doesn't exist!" %
                                        lf_name)
            self.lf_loaded.update({lf_name: lf})
            return [lf.name]
        else:
            return self.lf_loaded.keys()

    def lifecycle_by_name(self, lf_name):
        if self._autoload:
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

        :param state_xpath: A xpath that can match multiple states
        :param state_xpath: a xpath that matches states.
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

        :param lifecyle_xpath: A xpath that can match multiple lifecycles
        :rtype: [:class:`State`]
        """
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

        :param state_xpath: A xpath that can match multiple states
        :rtype: [(:py:class:`State`, [path])]

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

        :param state_xpath_uri: A xpath that matches a unique state.
        :param path_idx: (Not yet implemented)
        :rtype: [:py:class:`Provide`]

        """
        lf_name = XmlRegister.get_ressource(state_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(state_xpath_uri, "state")
        lf = self.lifecycle_by_name(lf_name)
        return lf.state_goto_requires(state_name)

    def state_goto(self, state_xpath_uri, requires={}, path_idx=0):
        """From the current state go to state.

        :param xpath: The xpath of a state. Must be unique.
        :type xpath: str
        :param requires: Requires needed to go to the target state
        :type requires: dict
        :rtype: None"""
        lf_name = XmlRegister.get_ressource(state_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(state_xpath_uri, "state")
        logger.debug("state-goto %s %s %s" % (
                     lf_name, state_name, requires))
        return self.lifecycle_by_name(lf_name).state_goto(state_name, requires)

    def provide(self, provide_xpath):
        """Provides that match provide_xpath.

        :param provide_xpath: xpath to provide
        :type provide_xpath: str

        :rtype: [:py:class:`Provide`]
        """
        matches = mss.xml_register.XmlRegister.find_all_elts(provide_xpath)
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
        :param path_idx: the path to use when there is multiple paths
            to go to the provide
        :type path_idx: int

        :rtype: [:py:class:`Provide`]
        """
        lf_name = XmlRegister.get_ressource(provide_xpath_uri, "lifecycle")
        state_name = XmlRegister.get_ressource(provide_xpath_uri, "state")
        return self.lifecycle_by_name(lf_name).provide_call_requires(state_name, path_idx)

    def provide_call_path(self, provide_xpath):
        """Paths for provides that matches provide_xpath.

        :param provide_xpath: xpath to provide
        :type provide_xpath: str

        :rtype: [(:py:class:`Provide`, [path, ...])]
        """
        matches = mss.xml_register.XmlRegister.find_all_elts(provide_xpath)
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

    def _format_input_variables(self, *variables_values):
        """Translate ("//xpath/to/variable_name", "value")
           to ("//xpath/to/variable_name", {0: "value"})
        """
        variables_values = list(itertools.chain(*variables_values))
        for index, (variable_xpath, variable_values) in enumerate(variables_values):
            if not type(variable_values) == dict:
                variables_values[index] = (variable_xpath, {0: variable_values})
        return variables_values

    def provide_call_validate(self, provide_xpath_uri, requires=[], path_idx=0):
        """Validate requires to call the provide

        :param xpath: The xpath og the provide to call
        :type xpath: str
        :param requires: A list of of tuples (variable_xpath, variable_values):
            variable_xpath is a full xpath
            variable_values is dict of index=value
        :type requires: list

        :rtype {'errors': bool, 'xpath': xpath, 'requires': [:class:`Provide`]}
        """
        variables_values = self._format_input_variables(requires)
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

        :param xpath: The xpath of the provide to call
        :type xpath: str
        :param requires: A list of of tuples (variable_xpath, variable_values):
            variable_xpath is a full xpath
            variable_values is dict of index=value
        :type requires: list
        """
        logger.debug("Provide call %s" % provide_xpath_uri)
        # be sure that the provide can be validated
        # we don't want to change states if we can't call the provide in the end
        if self.provide_call_validate(provide_xpath_uri, requires)['errors']:
            logger.error("Provided values doesn't met provide requires")
            raise ValidationError("Provided values doesn't met provide requires")
        requires = self._format_input_variables(requires)
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

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: dot file string"""
        return self.lifecycle_by_name(lf_name).to_dot(reachable=reachable)

    def to_primitive(self, lf_name, reachable=False):
        """Return the dot string of a lifecyle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: dot file string"""
        return self.lifecycle_by_name(lf_name).to_primitive(reachable=reachable)

    def uri(self, xpath="//"):
        """Return the list of uri that match this xpath.

        :param xpath: an xpath string
        :type xpath: str
        :rtype: [uri]"""
        return mss.xml_register.XmlRegister.find_all_elts(xpath)

    def from_xpath(self, xpath, ret="lifecycle"):
        """
        From a xpath try to get the object of type

        :param xpath: the xpath to a ressource
        :type xpath: str
        :param ret: the object to return (lifecycle, state, provide, require, variable)
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
        return mss.xml_register.XmlRegister.xpath(xpath)

    def to_xml(self, xpath=None):
        """Return the xml representation of agent."""
        return mss.xml_register.XmlRegister.to_string(xpath)
