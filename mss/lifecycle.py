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
transition between these states. See :class:`Lifecycle` for more
informations.

State
^^^^^^^^^^^^^^^^^^^^

A state describes actions on a service. For instance, a state can
describe packages installation, or configuration, etc. See
:class:`State` for more informations.

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

Code documentation
------------------
"""

import inspect
import logging

from mss.common import is_exposed, expose


logger = logging.getLogger(__name__)


class TransitionNotAllowed(Exception):
    pass


def Transition(s,d):
    return (s,d,)


class ProvideNotExist(Exception):
    pass
class ProvideNotInStack(Exception):
    pass
class ProvideAmbigous(Exception):
    pass


class Provide(object):
    def __init__(self, fct):
        """Build a provide from a provide function. This is used to
        return useful informations"""
        self.name = fct.__name__
        args = inspect.getargspec(fct)
        self.args = (args.args[1:], args.defaults)
        self.flags = fct._provide_flags

    def to_primitive(self):
        return {"name": self.name, "args": self.args, "flags": self.flags}

    def __repr__(self):
        return "<Provide:%s(%s,%s)>" % (self.name, self.args, self.flags)


def provide(flags={}):
    """This is a decorator to specify a method that can be used as a provide in a state.
    Be careful, without flags, this decorator should be used as following
    @provide()
    """
    def wrapper(func):
        func._provide = True
        func._provide_flags = flags
        return func

    return wrapper


class StateNotApply(Exception):
    pass
class StateNotExist(Exception):
    pass


class State(object):
    """A state describe a step during service :class:`Lifecycle`.

    It is possible to specify some requires. A require is a :class:`Require`
    which represents arguments required to entry in this state.

    To define a new state, it is necessary to redefine methods:
     :py:meth:`State.entry`
     :py:meth:`State.leave`
     :py:meth:`State.cross`
    """
    require_state = None
    requires = []
    """ """
    provides = []
    _lf_name = ""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(State, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

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

    def safe_entry(self, requires):
        """Check if all state requires are satisfated.

        :param requires: the requires for the state
        :type requires: {require_name1: [{value1: value, value2: value, ...}]}
        """
        for require in self.requires:
            if require.name in requires:
                values = requires[require.name]
                requires[require.name] = require.validate(values)
            else:
                requires.update({require.name: require.validate([])})
        logger.debug("applying state %s: %s" % (self.name, self.entry.__doc__))
        logger.debug("\trequires: %s" % requires)
        return self.entry(requires)

    def entry(self, requires):
        """Called when a state is applied

        :param requires: the requires for the state"""
        return "-> %s state entry" % self.name

    def leave(self):
        """Called when a state is leaved"""
        return "-> %s state leave" % self.name

    def cross(self, **kwargs):
        """Called when the state is traversed"""
        logger.info("%s.%-10s: cross state but nothing to do" % (self.lf_name, self.name))

    def entry_doc(self):
        """NOT YET IMPLEMENTED.
        By default, it returns doc string of entry method. You can
        override it to be more concise.

        TODO Need state to be built by LF in order to have an instance.
        """
        return self.entry.__doc__

    @classmethod
    def get_requires(cls):
        return cls.requires

    @classmethod
    def get_provides(cls):
        """Return a list of 3-uple (functionName, argsName, flags) """
        funcs = inspect.getmembers(cls, predicate=inspect.ismethod)
        acc = []
        for (fname, f) in funcs:
            try:
                if f._provide:
                    pass
            except AttributeError:
                continue
            acc.append(Provide(f))
        return acc

    @classmethod
    def _get_provide_by_name(cls, provide_name):
        for p in cls.get_provides():
            if p.name == provide_name:
                return p
        raise ProvideNotExist("%s doesn't exist in state %s" % (provide_name, cls.__name__))

    @classmethod
    def get_provide_args(cls, provide_name):
        return cls._get_provide_by_name(provide_name).args

    def get_provide_by_name(self, provide_name):
        return self.__class__._get_provide_by_name(provide_name)

    def __repr__(self):
        return "<State:%s>" % self.name


class Lifecycle(object):
    """The lifecycle of a service is represented by transitions,
    specified by class attribute :py:meth:`Lyfecycle.transition`,
    between :class:`State` classes. Moreover, this class remember
    which states have been applied in a stack, in order to be able
    able to unapply them.

    Main operations on a lifecycle are:

    * :py:meth:`Lifecycle.state_list` to list available states,
    * :py:meth:`Lifecycle.state_current` to know the current state,
    * :py:meth:`Lifecycle.state_goto` to go from current state to another state.
    * :py:meth:`Lifecycle.provide_call` to call a provide.

    All :class:`Lifecycle` method arguments 'state' can be a
    :class:`State` subclass or a string that describes this states
    (see :py:meth:`State.name`).

    The stack is considered by construction to be correct:
    - It doesn't contains two same states;

    """
    _initialized = False

    # _instance = None
    # def __new__(cls, *args, **kwargs):
    #     if not cls._instance:
    #         cls._instance = super(Lifecycle, cls).__new__(
    #             cls, *args, **kwargs) # FIXME: should not use Lifecycle
    #     return cls._instance

    def init(self, state, requires={}):
        """If it is not already initialized, push state in stack."""
        self._stack = []
        if not self._initialized:
            self._push_state(state, requires)
            self._initialized = True

    @property
    def name(self):
        return self.__class__.__name__

    def state_list(self):
        """To get all available states."""
        acc = []
        for (s, d) in self.transitions:
            if s not in acc: acc += [s]
            if d not in acc: acc += [d]
        return acc

    def state_current(self):
        """To get current state."""
        if self._stack == []:
            return None
        else:
            return self._stack[len(self._stack) - 1]

    def _is_state_in_stack(self,state):
        return self._get_state_class(state) in self._stack

    def _is_transition_allowed(self, s, d):
        return (s, d) in self.transitions

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
        logger.event({'event': 'state_appling', 'state': state.name, 'lifecycle': self.name})
        ret = state.safe_entry(requires)
        self._stack.append(state)
        logger.event({'event': 'state_applied', 'state': state.name, 'lifecycle': self.name})
        logger.debug("push state '%s'" % state)
        return ret

    def _pop_state(self):
        if self._stack != []:
            t = self._stack.pop()
            print t.leave()

    def _get_from_state_path(self, from_state, to_state, used_states=[], go_back=True):
        """From from_state state, return the path to go to the to_state
        state. Path is a list of 2-uple (state, "entry" or "leave")

        :param go_back: to allow state leaving
        """
        if from_state == to_state:
            return [] # It's not THE stop condition. Shity hack : FIXME !

        a = [(d, d, "entry") for (s, d) in self.transitions if s == from_state and d not in used_states]
        if go_back:
            a += [(s, d, "leave") for (s, d) in self.transitions if d == from_state and s not in used_states]
        # a = [( nextState , get_current_state , actionOnCurrentState )]
        for s in a:
            if s[0] == to_state:
                return [(s[1], s[2])]
            r = self._get_from_state_path(s[0], to_state, used_states + [s[0]])
            if r != [] and r[0][0] != s[1]: # To avoid [(S1,entry),(S1,leave),...]
                return [(s[1], s[2])] + r
        return []

    def state_goto(self, state, requires, go_back=True):
        """From current state, go to state. To know 'requires', call
        :py:meth:`Lifecycle.state_goto_requires`.  :py:meth:`State.entry` or
        :py:meth:`State.leave` of intermediate states are called
        depending of the presence of states in stack.

        :param requires: A dict of requires name and values. Value is a list of dict of variable_name:value ::

            {req1: [{variable1: value1, variable2: value2,...}, {variable1: value3, variable2: value4,...},...], req2: ...}

        :rtype: list of (state,["entry"|"leave"])

        """
        path = self.state_goto_path(state, go_back=go_back)
        if path == []:
            raise StateNotApply()
        for s in path:
            if s[1] == "entry":
                self._push_state(s[0], requires)
            elif s[1] == "leave":
                if self.state_current() == s[0]:
                    self._pop_state()
                else:
                    raise StateNotApply(self.state_current())

    def _get_state_class(self, state):
        """From a string state name or a state class, try to find the state object.

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

    def state_goto_path(self, state, fct=None, go_back=True):
        """From the current state, return the path to goto the state.
        If fct is not None, fct is applied on each state on the path.
        state arg is preprocessed by _get_state_class method. It then can be a str or a class.
        """
        state = self._get_state_class(state)
        logger.debug("get_state_path state '%s'" % state)
        r = self._get_from_state_path(self.state_current(), state, go_back=go_back)
        if fct != None:
            for state in r:
                fct(state[0])
        return r

    def state_goto_requires(self, state, go_back=True):
        """Return all requires needed to go from current state to state."""
        acc = []
        for s in self.state_goto_path(state, go_back=go_back):
            if s[1] == "entry":
                acc += s[0].get_requires()
        return acc

    def provide_list_in_stack(self):
        """:rtype: the list of states and provides for the current stack."""
        return [(s, s.get_provides()) for s in self._stack if s.get_provides() != []]

    def provide_list(self):
        """:rtype: the list of all states and provides."""
        return [(s, s.get_provides()) for s in self.state_list() if s.get_provides() != []]

    def _get_state_from_provide(self, provide_name):
        """From a provide_name, return a tuple of (state, provide_name).
        provide_name can be fully qualified, ie. state.provide_name."""
        p = provide_name.split(".")
        if len(p) == 1: # Simple provide name
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
        elif len(p) == 2: # Fully qualified provide name
            s = self._get_state_class(p[0])
            s.get_provide_by_name(p[1])
            return (p[0],p[1])

    def provide_call_requires(self, provide_name):
        """From a provide_name, return the list of "requires" needed to
        apply the state which provides provide_name."""
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            return self.state_goto_requires(s)
        else:
            return []

    def provide_call_args(self, provide_name):
        """From a provide_name, returns its needed arguments."""
        (s, p) = self._get_state_from_provide(provide_name)
        return s.get_provide_args(p)

    def provide_call_path(self, provide_name):
        """From a provide_name, return the path to the state that
        provides the "provide"."""
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            return self.state_goto_path(s)
        else:
            return []

    def provide_call(self, provide_name, requires, provide_args):
        """Call a provide and go to provider state if needed.

        :param provide_name: The name (simple or fully qualified) of the provide
        :param requires: Requires needed to reach the state that provides this provide.
                         See :py:meth:`Lifecycle.state_goto` for more informations
        :param provide_args: Args needed by this provide

        """
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            self.state_goto(s, requires)
        return self.provide_call_in_stack(s, p, provide_args)

    def provide_call_in_stack(self, state, provide_name, provide_args):
        """Call a provide by name. State which provides must be in the stack.
        TODO: Use full qualified name when a provide is ambigous: State.provide
        """
        state = self._get_state_class(state)
        sidx = self._stack.index(state)
        p = state.get_provide_by_name(provide_name)
        sfct = state.__getattribute__(p.name)
        ret = sfct(**provide_args)
        for i in self._stack[sidx:]:
            i.cross(**(p.flags))
        return ret

    def to_dot(self):
        """Return a dot string of lifecycle."""

        def dotify(string): # To remove illegal character
            return string.replace("{","").replace("}","") # string.replace("[","").replace("]","")

        def list_to_table(l):
            if l == []:
                acc = ""
            else:
                acc = dotify(str(l[0]))
                if len(l) > 1:
                    for a in l[1:]:
                        acc += "| %s" % dotify(str(a))
            return acc

        acc = ""
        acc += "digraph finite_state_machine {\n"
        acc += "node [shape = ellipse];\n"
        for s in self.state_list():
            acc += '"%s"[\n' % s.name
            acc += 'shape = "record"\n'
            requires = ""
            requires = list_to_table([r.to_primitive() for r in s.get_requires()])
            provides = list_to_table([(p.name, p.args, p.flags) for p in s.get_provides()])
            label = 'label = "{State name: %s  | Method entry: %s | Method leave : %s | {Method cross: | {Doc: %s | Flags: %s}} | { Requires: | {%s} } | { Provides: | {%s}}}"\n' % (
                s.name,
                s.entry.__doc__,
                s.leave.__doc__,
                s.cross.__doc__,
                inspect.getargspec(s.cross).args[1:],
                requires,
                provides
            )
            acc += label
            acc += "];\n"
        for (s, d) in self.transitions:
            acc += "%s -> %s;\n" % (s.name, d.name)
        acc += "}\n"
        return acc

    def __repr__(self):
        return "<Lifecycle:%s>" % self.name


class LifecycleNotExist(Exception):
    pass


class LifecycleManager(object):
    """This is the high level object. It permits to load lifecycles, know
    which lifecycles are loaded and interact with loaded lifecycles.

    All methods of this class takes and returns primitive types (ie str)
    in order to be send over network.
    """
    def __init__(self, autoload=True):
        self._autoload = autoload
        self.lf_loaded = {}
        self.lf = {}
        for lf in Lifecycle.__subclasses__():
            self.lf.update({lf.__name__: lf})

    def _dispatch(self, method, *args, **kwargs):
        """Method used by the agent to query :py:class:`LifecycleManager` methods.
        Only exposed methods are available through the agent.
        """
        func = getattr(self, method)
        if not is_exposed(func):
            raise Exception('Method "%s" is not supported' % method)
        return func(*args, **kwargs)

    @expose
    def list(self):
        """List loaded lifecycle objects

        :rtype: list of strings (lifecycle objects names)
        """
        return self.lf.keys()

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
            except KeyError:
                raise LifecycleNotExist("Lifecycle '%s' doesn't exist!" % lf_name)
            self.lf_loaded.update({lf_name: lf})
            return [lf.name]
        else:
            return self.lf_loaded.keys()

    def get_by_name(self, lf_name):
        if self._autoload:
            try:
                self.lf_loaded[lf_name]
            except KeyError:
                self.load(lf_name)
        return self.lf_loaded[lf_name]

    @expose
    def state_list(self, lf_name, doc=False):
        """Return all available states of the lifecycle object

        :param lf_name: The name of the lifecycle object
        :param doc: Add state documentation
        :type lf_name: str
        :type verbose: bool
        :rtype: list of strings (states names)"""
        if doc:
            return [{'name':s.name,'doc':s.__doc__} for s in self.get_by_name(lf_name).state_list()]
        else:
            return [s.name for s in self.get_by_name(lf_name).state_list()]
        
    @expose
    def state_current(self, lf_name):
        """Get the current state name of the lifecycle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: name of the state
        """
        return self.get_by_name(lf_name).state_current().name

    @expose
    def state_goto_path(self, lf_name, state_name):
        """From the current state, return the path to goto the state of the
        lifecycle object.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param state_name: The name of the state
        :type state_name: str
        :rtype: list of transitions"""
        return [(i[0].name, i[1]) for i in self.get_by_name(lf_name).state_goto_path(state_name)]

    @expose
    def state_goto_requires(self, lf_name, state_name):
        """Get the lifecycle state's requires

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param state_name: The name of the state
        :type state_name: str
        :rtype: dict of requires"""
        return self.get_by_name(lf_name).state_goto_requires(state_name)

    @expose
    def state_goto(self, lf_name, state_name, requires={}):
        """From the current state go to state.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param state_name: The name of the state to go to
        :type state_name: str
        :param requires: Requires needed to go to the target state
        :type requires: dict"""
        return self.get_by_name(lf_name).state_goto(state_name, requires)

    @expose
    def provide_list(self, lf_name, in_stack=False):
        """If in_stack is True, just returns provides available in
        stack. Otherwise, returns all provides of this lf_name.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param in_stack: True or False (default)
        :type in_stack: bool"""
        acc = {}
        if in_stack:
            ps = self.get_by_name(lf_name).provide_list_in_stack()
        else:
            ps = self.get_by_name(lf_name).provide_list()
        for (s, p) in ps:
            acc.update({s.name: [i.to_primitive() for i in p]})
        return acc

    @expose
    def provide_call_requires(self, lf_name, provide_name):
        """From a provide_name, return the list of "requires" needed to
        apply the state which provides provide_name.

        :param lf_name: The name of the lifecycle object
        :param provide_name: The name of the provide"""
        return self.get_by_name(lf_name).provide_call_requires(provide_name)

    @expose
    def provide_call_args(self, lf_name, provide_name):
        """From a provide_name, returns its needed arguments.

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param provide_name: The name of the provide
        :type provide_name: str"""
        return self.get_by_name(lf_name).provide_call_args(provide_name)

    @expose
    def provide_call_path(self, lf_name, provide_name):
        """From a provide_name, return the path to the state of the lifecycle that
        provides the "provide".

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param provide_name: The name of the provide
        :type provide_name: str"""
        return [(s.name, a) for (s, a) in self.get_by_name(lf_name).provide_call_path(provide_name)]

    @expose
    def provide_call(self, lf_name, provide_name, requires={}, provide_args={}):
        """Call a provide of a lifecycle and go to provider state if needed

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :param provide_name: The name of the provide to go to
        :type provide_name: str
        :param requires: Requires needed to reach the state that provides this provide
                         See :py:meth:`Lifecycle.state_goto` for more information
        :type requires: dict
        :param provide_args: Args needed by this provide
        :type provide_args: dict"""
        return self.get_by_name(lf_name).provide_call(provide_name, requires, provide_args)

    @expose
    def to_dot(self, lf_name):
        """Return the dot string of a lifecyle object

        :param lf_name: The name of the lifecycle object
        :type lf_name: str
        :rtype: dot file string"""
        return self.get_by_name(lf_name).to_dot()
