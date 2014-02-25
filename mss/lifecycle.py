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

from mss.common import is_exposed, expose, IterContainer, DoesNotExist
from mss.require import Requires, Require
from mss.variable import VString
import mss.utils

from xml_register import XmlRegister, XpathHaveNotRessource, Element, SubElement

logger = logging.getLogger(__name__)
STATE_RESERVED_METHODS = ('entry', 'leave', 'cross')


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
        args = inspect.getargspec(func)
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
    """A state describe a step during service :class:`Lifecycle`.

    It is possible to specify some requires. A require is a :class:`Require`
    which represents arguments required to entry in this state.

    To define a new state, it is necessary to redefine methods:
     :py:meth:`State.entry`
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
            cls._provides = []
            for method in STATE_RESERVED_METHODS:
                setattr(cls, "_requires_%s" % method, Requires(method, []))

            funcs = inspect.getmembers(cls, predicate=inspect.ismethod)
            for (fname, f) in funcs:
                if hasattr(f, '_requires'):
                    if f.__name__ in STATE_RESERVED_METHODS:
                        r = Requires(f.__name__, f._requires)
                        setattr(cls, "_requires_%s" % f.__name__, r)
                    else:
                        flags = f._flags if hasattr(f, '_flags') else {}
                        r = Requires(f.__name__, f._requires, flags)
                        cls._provides.append(r)

                    logger.debug("Create a Requires for %s.%s with Require %s" % (cls.__name__, f.__name__, [t.name for t in r]))

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

    def safe_entry(self, primitive):
        """Check if all state requires are satisfated.

        :param primitive: values for all requires of the State.
        See :py:meth:`Requires.build_from_primivitive` for more informations.
        :type primitive: {require1: {variable1: value, variable2: value},
            require2: ...}
        """
        self.requires_entry.build_from_primitive(primitive)
        return self.entry()

    def entry(self):
        """Called when a state is applied"""
        return "-> %s state entry" % self.name

    def leave(self):
        """Called when a state is leaved"""
        return "-> %s state leave" % self.name

    def cross(self, **kwargs):
        """Called when the state is traversed"""
        logger.info("State crossed but nothing to do.")

    def entry_doc(self):
        """NOT YET IMPLEMENTED.
        By default, it returns doc string of entry method. You can
        override it to be more concise.

        TODO Need state to be built by LF in order to have an instance.
        """
        return self.entry.__doc__

    @property
    def requires_entry(self):
        """
        Requires to enter the state

        :rtype: Requires
        """
        return self._requires_entry

    @property
    def requires_leave(self):
        """
        Requires to leave the state

        :rtype: Requires
        """
        return self._requires_leave

    @property
    def requires_cross(self):
        """
        Requires to cross the state

        :rtype: Requires
        """
        return self._requires_cross

    @property
    def provides(self):
        """
        Requires for all provides

        :rtype: [Requires]
        """
        return self._provides

    def provide_args(self, provide_name):
        """
        Requires for the provide

        :rtype: Requires
        """
        for p in self.provides:
            if p.name == provide_name:
                return p
        raise ProvideNotExist("%s doesn't exist in state %s" %
                              (provide_name, self.__name__))

    def __repr__(self):
        return "<State:%s>" % self.name

    def to_primitive(self):
        return {"name": self.name,
                "xpath": self.get_xpath_relative(),
                "supported_os_type": [t.to_primitive() for t in
                                      self.supported_os_type],
                "provides": [r.to_primitive() for r in self.provides],
                "requires_entry": self.requires_entry.to_primitive()}


class MetaState(State):
    """Set by state.__new__ to add implementation of this metastate."""
    implementations = []


class Lifecycle(XmlRegister):
    """The lifecycle of a service is represented by transitions,
    specified by class attribute :py:meth:`Lyfecycle.transition`,
    between :class:`State` classes. Moreover, this class remember
    which states have been applied in a stack, in order to be able
    able to unapply them.

    Main operations on a lifecycle are:

    * :py:meth:`Lifecycle.state_list` to list available states,
    * :py:meth:`Lifecycle.state_current` to know the current state,
    * :py:meth:`Lifecycle.state_goto` to go from current state to another
                state.
    * :py:meth:`Lifecycle.provide_call` to call a provide.

    All :class:`Lifecycle` method arguments 'state' can be a
    :class:`State` subclass or a string that describes this states
    (see :py:meth:`State.name`).

    The stack is considered by construction to be correct:
    - It doesn't contains two same states;

    """
    _initialized = False

    os_type = mss.utils.OS_TYPE
    """To specify the current os_type. By default, os type is
    automatically discovered but it is possible to overlap this
    attribute to manually specify one.
    """
    abstract = False
    """If the Lifecycle is abstract it won't be load in the LifecycleManager
    and ine the XML registery.
    """

    def __new__(cls):
        instance = super(Lifecycle, cls).__new__(
            cls)

        # Update transitions to manage MetaState
        for ms in instance._state_list():
            # For each MetaState ms
            if isinstance(ms, MetaState):
                transitions = [(s, i) for (s, i) in
                               instance.transitions if i == ms]
                states = ms.implementations

                # We create new state suffixed by metaclass name This
                # permits to create specical path.  If two metastate
                # has same implementation, we need to create special
                # implementations for each metastate.
                created_states = [type(
                    '%s.%s' % (ms.__class__.__name__, s.__name__),
                    (s,),
                    {}) for s in ms.implementations]
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
        acc = []
        for (s, d) in cls.transitions:
            if s not in acc:
                acc += [s]
            if d not in acc:
                acc += [d]
        return acc

    def state_list(self, reachable=False):
        """To get all available states.

        :parama reachable: list reachable states from the current state.
        :rtype: list of states.
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
        """To get current state."""
        if self._stack == []:
            return None
        else:
            return self._stack[len(self._stack) - 1]

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
            cstate = self._stack[len(self._stack) - 1]
            if not self._is_transition_allowed(cstate, state):
                raise TransitionNotAllowed("from %s to %s" % (cstate, state))
        state.lf_name = self.name
        logger.event({'event': 'state_appling',
                      'state': state.name,
                      'lifecycle': self.name})
        ret = state.safe_entry(requires)
        self._stack.append(state)
        logger.event({'event': 'state_applied',
                      'state': state.name,
                      'lifecycle': self.name})
        logger.debug("push state '%s'" % state.get_xpath())
        return ret

    def _pop_state(self):
        if self._stack != []:
            t = self._stack.pop()
            print t.leave()

    def _get_from_state_paths(self, from_state, to_state):
        logger.debug("Find paths from %s to %s" % (from_state, to_state))
        paths = []

        def _find_prev_state(state, paths, path):
            for (src, dst) in self.transitions:
                if dst == state:
                    new_path = copy.copy(path)
                    new_path.append(src)
                    paths.append(new_path)
                    if not src == from_state:
                        _find_prev_state(src, paths, new_path)
            # we can't go further
            # should we keep this path ?
            if not (path[0] == from_state and path[-1] == to_state):
                # seems not! delete it
                for i, p in enumerate(paths):
                    if p == path:
                        del paths[i]

        # trying to find a path from "to_state" to "from_state"
        # meaning we are going forward in the state machine
        _find_prev_state(to_state, paths, path=[to_state])
        if len(paths) > 0:
            # ok we found some paths !
            paths = [list(reversed(path)) for path in paths]
            # setup state methods
            for path in paths:
                for i, state in enumerate(path):
                    if i == 0:
                        path[i] = (state, "leave")
                    else:
                        path[i] = (state, "entry")
        # no path found, trying to go backwards in the state machine
        # from "from_state" to "to_state"
        else:
            _find_prev_state(from_state, paths, path=[from_state])
            # setup state methods
            for path in paths:
                for i, state in enumerate(path):
                    if i == (len(path) - 1):
                        path[i] = (state, "entry")
                    else:
                        path[i] = (state, "leave")

        logger.debug("Found paths:\n%s" % pprint.pformat(paths))
        return paths

    def state_goto(self, state, requires, path_index=0):
        """From current state, go to state. To know 'requires', call
        :py:meth:`Lifecycle.state_goto_requires`.  :py:meth:`State.entry` or
        :py:meth:`State.leave` of intermediate states are called
        depending of the presence of states in stack.

        :param requires: A dict of requires name and values. Value is a list of
        dict of variable_name:value ::

            {req1: [{variable1: value1, variable2: value2,...},
            {variable1: value3, variable2: value4,...},...], req2: ...}

        :rtype: list of (state,["entry"|"leave"])

        """
        logger.debug("Goto state %s using path %i" % (state, path_index))
        path = self.state_goto_path(state, path_index=path_index)
        for s in path:
            if s[1] == "entry":
                self._push_state(s[0], requires)
            elif s[1] == "leave":
                if self.state_current() == s[0]:
                    self._pop_state()
                else:
                    raise StateNotApply(self.state_current())

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
        """Get a state from its name

        :param name: the name of a state
        :rtype: State or None (if state doesn't exist)
        """
        for s in self.state_list():
            if s.name == name:
                return s

    def has_state(self, state):
        """To know if state_name is a state of self."""
        self._get_state_class(state)
        return True

    def state_goto_path_list(self, state):
        """From the current state return the list of paths to go to the state.
        """
        state = self._get_state_class(state)
        logger.debug("Get paths to go to state %s" % state)
        return self._get_from_state_paths(self.state_current(), state)

    def state_goto_path(self, state, fct=None, path_index=0):
        """From the current state, return the path to goto the state.
        If fct is not None, fct is applied on each state on the path.
        state arg is preprocessed by _get_state_class method. It then can be a
        str or a class.
        """
        try:
            path = self.state_goto_path_list(state)[path_index]
        except IndexError:
            raise StateNotApply()
        if fct is not None:
            for state in path:
                fct(state[0])
        return path

    def state_goto_requires(self, state, path_index=0):
        """Return all requires needed to go from current state to state.
        :param state: The state where we want to goto
        :type state: a state name or a state class
        :rtype: [Require]
        """
        acc = []
        for s in self.state_goto_path(state, path_index=path_index):
            if s[1] == "entry":
                r = s[0].requires_entry
                acc += r if r is not None else []
        return acc

    def provide_list_in_stack(self):
        """:rtype: the list of states and provides for the current stack."""
        return [(s, s.provides) for s in
                self._stack if s.provides != []]

    def provide_list(self):
        """Return the list of all tuple which contain states and provides.
        :rtype: [(State, [Requires])]"""
        return [(s, s.provides) for s in
                self.state_list() if s.provides != []]

    def _get_state_from_provide(self, provide_name):
        """
        DEPRECATED
        From a provide_name, return a tuple of (state, provide_name).
        provide_name can be fully qualified, ie. state.provide_name.

        :param provide_name: the name of a provide (can be fully qualified or
            not)
        :rtype: (state, provide_name)
        """
        p = provide_name.split(".")
        if len(p) == 1:  # Simple provide name
            sp = []
            for (s, ps) in self.provide_list():
                for p in ps:
                    if p.name == provide_name:
                        sp.append((s, provide_name))
            if sp == []:
                raise ProvideNotExist()
            elif len(sp) > 1:
                raise ProvideAmbigous("You should full qualify it!")
            elif len(sp) == 1:
                return (sp[0])
        elif len(p) == 2:  # Fully qualified provide name
            s = self._get_state_class(p[0])
            s.provide_args(p[1])
            return (s, p[1])

    def provide_call_requires(self, state_name):
        """From a provide_name, return the list of "requires" needed to
        apply the state which provides provide_name.

        Note: this method should be useless. We should use
        state_goto_requires instead!
        """
        state = self._get_state_class(state_name)
        if not self._is_state_in_stack(state):
            return self.state_goto_requires(state)
        else:
            return []

    def provide_call_args(self, state_name, provide_name):
        """From a provide_name, returns its needed arguments."""
        state = self._get_state_class(state_name)
        # To be sure that the provide exists
        state.provide_args(provide_name)
        return state.provide_args(provide_name)

    def provide_call_path(self, state_name):
        """From a provide_name, return the path to the state that
        provides the "provide".

        Note: this method should be useless. We should use
        state_goto_requires instead!
        """
        state = self._get_state_class(state_name)
        if not self._is_state_in_stack(state):
            return self.state_goto_path(state)
        else:
            return []

    def provide_call(self, state_name, provide_name, requires, provide_args):
        """Call a provide and go to provider state if needed.

        :param provide_name: The name (simple or fully qualified) of the
            provide
        :param requires: Requires needed to reach the state that provides this
            provide.
                         See :py:meth:`Lifecycle.state_goto` for more
                         informations
        :param provide_args: Args needed by this provide

        """
        state = self._get_state_class(state_name)
        # To be sure that the provide exists
        state.provide_args(provide_name)
        if not self._is_state_in_stack(state):
            self.state_goto(state, requires)
        return self.provide_call_in_stack(state, provide_name, provide_args)

    def provide_call_in_stack(self, state, provide_name, provide_args):
        """Call a provide by name. State which provides must be in the stack.
        TODO: Use full qualified name when a provide is ambigous: State.provide
        """
        state = self._get_state_class(state)
        sidx = self._stack.index(state)
        p = state.provide_args(provide_name)
        sfct = state.__getattribute__(p.name)
        # args = p.build_args_from_primitive(provide_args)
        p.build_from_primitive(provide_args)
        ret = sfct(p)
        logger.debug("Provide %s returns values %s" % (
            p.name, ret))
        for i in self._stack[sidx:]:
            i.cross(**(p.flags))
        return ret

    def to_dot(self, cross=False,
               enter_doc=False,
               leave_doc=False,
               reachable=False):
        """Return a dot string of lifecycle."""

        def dotify(string):  # To remove illegal character
            if string != None:
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
            requires = ""
            provides = list_to_table([(p.name, p.flags) for p in
                                      s.get_provides()])
            # Begin of label
            acc += 'label = "{%s | %s ' % (
                s.name,
                dotify(s.__doc__),
            )
            # Enter doc
            if enter_doc:
                acc += " | Entry: %s" % (dotify(s.entry.__doc__))
            if leave_doc:
                acc += " | Leave: %s" % (dotify(s.leave.__doc__))
            # Cross method
            if cross:
                acc += "| {Cross: | {Doc: %s | Flags: %s}}" % (
                    dotify(s.cross.__doc__),
                    inspect.getargspec(s.cross).args[1:])
            # Enter Requires
            acc += "| { enter\l | {%s}}" % list_to_table([r.name for r in
                                                          s.requires_entry])
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
    """This is the high level object. It permits to load lifecycles, know
    which lifecycles are loaded and interact with loaded lifecycles.

    All methods of this class takes and returns primitive types (ie str)
    in order to be send over network.

    :param autoload: TODO
    :param modules_dir: the path of the modules root directory
    :param include_modules: the list of wanted modules
    :param os_type: to specify which kind of os has to be used.\
    If it is not specified, the os type is automatically discovered.
    """
    def __init__(self, autoload=True, modules_dir=None, include_modules=None, os_type=None):
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
                lf()._xml_register()
            else:
                logger.debug("Ignoring abstract Lifecycle %s" % lf)

    def _dispatch(self, method, *args, **kwargs):
        """Method used by the agent to query :py:class:`LifecycleManager`
        methods.
        Only exposed methods are available through the agent.
        """
        func = getattr(self, method)
        if not is_exposed(func):
            raise Exception('Method "%s" is not supported' % method)
        return func(*args, **kwargs)

    @expose
    def info(self):
        """Get info of mss agent

        :rtype: list of strings (lifecycle objects names)
        """
        return {"os-type": mss.utils.OS_TYPE.name,
                "os-release": mss.utils.OS_TYPE.release}

    @expose
    def lifecycle(self, xpath, doc=False):
        """List loaded lifecycle objects

        :rtype: list of strings (lifecycle objects names)
        """
        elts = XmlRegister.find_all_elts(xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            lf = self._get_by_name(lf_name)
            if doc:
                acc.append({"name": lf_name,
                            "doc": lf.__class__.__doc__,
                            "xpath": lf.get_xpath()})
            else:
                acc.append(lf_name)
        return acc

    def load(self, lf_name=None):
        """Load a lifecycle object in the manager.
        If lf_name is not set, return a list of loaded LF.

        :param lf_name: the lifecycle to load
        :type lf_name: str
        :rtype: list of lifecycle objects names
        """
        if lf_name != None:
            try:
                lf = self.lf[lf_name]()
                if self.os_type is not None:
                    lf.os_type = self.os_type
            except KeyError:
                raise LifecycleNotExist("Lifecycle '%s' doesn't exist!" %
                                        lf_name)
            self.lf_loaded.update({lf_name: lf})
            return [lf.name]
        else:
            return self.lf_loaded.keys()

    def _get_by_name(self, lf_name):
        if self._autoload:
            try:
                self.lf_loaded[lf_name]
            except KeyError:
                self.load(lf_name)
        try:
            return self.lf_loaded[lf_name]
        except KeyError:
            raise LifecycleNotExist("%s is not loaded" % lf_name)

    @expose
    def state(self, xpath, doc=False):
        """Return state accordgin to the xpath.

        :param doc: Add state documentation
        :param xpath: A xpath that match state ressources
        :type xpath: str
        :rtype: list of strings (states xpath) or list of dict (if doc is True)
        """
        elts = XmlRegister.find_all_elts(xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            state_name = XmlRegister.get_ressource(e, "state")
            state = self._get_by_name(lf_name)._get_state_class(state_name)
            if doc:
                acc.append(state.to_primitive())
            else:
                acc.append(e)
        return acc

    @expose
    def state_current(self, xpath):
        """Get the current state name of the lifecycle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: name of the state
        """
        elts = XmlRegister.find_all_elts(xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            lf = self._get_by_name(lf_name)
            acc.append({"xpath": e, "state": lf.state_current().name})
        return acc

    @expose
    def state_goto_path(self, xpath):
        """From the current state, return the path to goto the state of the
        lifecycle object.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param state_name: The name of the state
        :type state_name: str
        :rtype: list of transitions"""
        elts = XmlRegister.find_all_elts(xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            state_name = XmlRegister.get_ressource(e, "state")
            state = self._get_by_name(lf_name)._get_state_class(state_name)
            acc.append({'xpath': e,
                        'actions': [(i[0].name, i[1]) for i in self._get_by_name(lf_name).state_goto_path(state_name)]})
        return acc

    @expose
    def state_goto_requires(self, xpath):
        """Get the lifecycle state's requires

        :param xpath: A xpath that match states
        :type xpath: str
        :rtype: dict of requires"""
        elts = XmlRegister.find_all_elts(xpath)
        acc = []
        for e in elts:
            lf_name = XmlRegister.get_ressource(e, "lifecycle")
            state_name = XmlRegister.get_ressource(e, "state")
            state = self._get_by_name(lf_name)._get_state_class(state_name)
            acc.append({'xpath': e,
                        'requires': self._get_by_name(lf_name).state_goto_requires(state_name)})
        return acc

    @expose
    def state_goto(self, xpath, requires={}):
        """From the current state go to state.

        :param xpath: The xpath of a state. Must be unique.
        :type xpath: str
        :param requires: Requires needed to go to the target state
        :type requires: dict"""
        lf_name = XmlRegister.get_ressource(xpath, "lifecycle")
        state_name = XmlRegister.get_ressource(xpath, "state")
        logger.debug("state-goto %s %s %s" % (
                lf_name, state_name, requires))
        return self._get_by_name(lf_name).state_goto(state_name, requires)

    @expose
    def provide(self, xpath):
        """Returns all provides of this lf_name.

        :param xpath: The xpath of a provide.
        :type xpath: str
        """
        matches = mss.xml_register.XmlRegister.find_all_elts(xpath)
        acc = []
        for m in matches:
            if XmlRegister.is_ressource(m, "provide"):
                provide_name = XmlRegister.get_ressource(m, "provide")
                if provide_name not in STATE_RESERVED_METHODS:
                    lf_name = XmlRegister.get_ressource(m, "lifecycle")
                    state_name = XmlRegister.get_ressource(m, "state")
                    acc.append(self._get_by_name(lf_name).state_by_name(state_name).provide_args(provide_name))
        return acc

    @expose
    def provide_call_requires(self,
                              lf_name=None,
                              provide_name=None,
                              xpath=None):
        """From a provide_name, return the list of "requires" needed to
        apply the state which provides provide_name.

        :param lf_name: The name of the lifecycle object
        :param provide_name: The name of the provide"""
        if xpath != None:
            lf_name = XmlRegister.get_ressource(xpath, "lifecycle")
            state_name = XmlRegister.get_ressource(xpath, "state")
            provide_name = XmlRegister.get_ressource(xpath, "provide")
        return self._get_by_name(lf_name).provide_call_requires(state_name)

    @expose
    def provide_call_args(self, lf_name=None, provide_name=None, xpath=None):
        """From a provide_name, returns its needed arguments.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param provide_name: The name of the provide
        :type provide_name: str"""
        if xpath != None:
            lf_name = XmlRegister.get_ressource(xpath, "lifecycle")
            state_name = XmlRegister.get_ressource(xpath, "state")
            provide_name = XmlRegister.get_ressource(xpath, "provide")
        return self._get_by_name(lf_name).provide_call_args(state_name,
                                                            provide_name)

    @expose
    def provide_call_path(self, xpath=None):
        """From a provide_name, return the path to the state of the lifecycle
        that provides the "provide".

        :param xpath: The xpath of provides
        :type lf_name: str
        :param provide_name: The name of the provide
        :type provide_name: str"""
        matches = mss.xml_register.XmlRegister.find_all_elts(xpath)
        acc = []
        for m in matches:
            if XmlRegister.is_ressource(m, "provide"):
                provide_name = XmlRegister.get_ressource(m, "provide")
                if provide_name not in STATE_RESERVED_METHODS:
                    lf_name = XmlRegister.get_ressource(m, "lifecycle")
                    state_name = XmlRegister.get_ressource(m, "state")
                    acc.append({"xpath": m,
                                "actions": [(s.name, a) for (s, a) in self._get_by_name(lf_name).provide_call_path(state_name)]})
        return acc

    @expose
    def provide_call(self,
                     xpath,
                     requires={},
                     provide_args={}):
        """Call a provide of a lifecycle and go to provider state if needed

        :param xpath: The xpath of provides
        :type xpath: str
        :param requires: Requires needed to reach the state that provides this
                         provide
                         See :py:meth:`Lifecycle.state_goto` for more
                         information
        :type requires: dict
        :param provide_args: Args needed by this provide
        :type provide_args: dict"""
        lf_name = XmlRegister.get_ressource(xpath, "lifecycle")
        state_name = XmlRegister.get_ressource(xpath, "state")
        provide_name = XmlRegister.get_ressource(xpath, "provide")
        logger.debug("provide-call %s %s %s %s" % (
                lf_name, provide_name, requires, provide_args))
        return self._get_by_name(lf_name).provide_call(state_name,
                                                       provide_name,
                                                       requires,
                                                       provide_args)

    @expose
    def to_dot(self, lf_name, reachable=False):
        """Return the dot string of a lifecyle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: dot file string"""
        return self._get_by_name(lf_name).to_dot(reachable=reachable)

    @expose
    def to_primitive(self, lf_name, reachable=False):
        """Return the dot string of a lifecyle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: dot file string"""
        return self._get_by_name(lf_name).to_primitive(reachable=reachable)

    @expose
    def uri(self, xpath="//"):
        """Return the list of uri that match this xpath.

        :param xpath: an xpath string
        :type xpath: str
        :rtype: [uri]"""
        return mss.xml_register.XmlRegister.find_all_elts(xpath)

    @expose
    def xpath(self, xpath):
        return mss.xml_register.XmlRegister.xpath(xpath)

    @expose
    def to_xml(self, xpath=None):
        """Return the xml representation of agent."""
        return mss.xml_register.XmlRegister.to_string(xpath)
