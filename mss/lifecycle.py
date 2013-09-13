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
        args=inspect.getargspec(fct)
        self.args = (args.args[1:],args.defaults)
        self.flags = fct._provide_flags

    def to_primitive(self):
        return {"name":self.name, "args":self.args, "flags":self.flags}

    def __repr__(self):
        return "%s(%s,%s)" % (self.name, self.args, self.flags)


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
     :py:meth:`leave`
     :py:meth:`cross`
    """
    require_state = None
    requires = []
    """ """
    provides = []
    _module = ""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(State, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def safe_entry(self, requires):
        """Check if all state requires are satisfated.

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
        """Called when a state is applied"""
        return "-> %s state entry" % self.__class__.__name__

    def leave(self):
        """Called when a state is leaved"""
        return "-> %s state leave" % self.__class__.__name__

    def cross(self, **kwargs):
        """Called when the state is traversed"""
        logger.info("%s.%-10s: cross state but nothing to do" % (self.module(), self.name))

    @property
    def name(self):
        return self.__class__.__name__

    def entry_doc(self):
        """NOT YET IMPLEMENTED.
        By default, it returns doc string of entry method. You can
        override it to be more concise.

        TODO Need state to be built by LF in order to have an instance.
        """
        return self.entry.__doc__

    def module(self):
        """Shity hack. This return the name of module using this
        state. It is set by LF push method.
        """
        return self._module

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
    def get_provide_args(cls,provide_name):
        return cls._get_provide_by_name(provide_name).args
    @classmethod
    def _get_provide_by_name(cls, provide_name):
        for p in cls.get_provides():
            if p.name == provide_name:
                return p
        raise ProvideNotExist("%s doesn't exist in state %s" % (provide_name, cls.__name__))

    def get_provide_by_name(self, provide_name):
        return self.__class__._get_provide_by_name(provide_name)

    def __repr__(self):
        return self.name


class Lifecycle(object):
    """The lifecycle of a service is represented by transitions,
    specified by class attribute :py:meth:`Lyfecycle.transition`,
    between :class:`State` classes. Moreover, this class remember
    which states have been applied in a stack, in order to be able
    able to unapply them.

    Main operations on a lifecycle are:

    * :py:meth:`Lifecycle.get_states` to list available states,
    * :py:meth:`Lifecycle.get_current_state` to know the current state,
    * :py:meth:`Lifecycle.goto_state` to go from current state to another state.
    * :py:meth:`Lifecycle.call_provide` to call a provide.

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

    def get_states(self):
        """To get all available states."""
        acc=[]
        for (s, d) in self.transitions:
            if s not in acc: acc += [s]
            if d not in acc: acc += [d]
        return acc

    def get_current_state(self):
        """To get current state."""
        if self._stack == []:
            return None
        else:
            return self._stack[len(self._stack) - 1]

    def _is_state_in_stack(self,state):
        return self._get_state_class(state) in self._stack

    def _is_transition_allowed(self, s, d):
        return (s, d) in self.transitions

    def _push_state(self,state,requires):
        """Go to a state if transition from current state to state is allowed
        TODO: verify that state is not in stack yet.
        You should never use this method. Use goto_state instead.
        """
        if self._stack != []:
            cstate = self._stack[len(self._stack) - 1]
            if not self._is_transition_allowed(cstate, state):
                raise TransitionNotAllowed("from %s to %s" % (cstate, state))
        state._module = self.name
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

    def goto_state(self, state, requires, go_back=True):
        """From current state, go to state. To know 'requires', call
        :py:meth:`Lifecycle.get_state_requires`.  :py:meth:`State.entry` or
        :py:meth:`State.leave` of intermediate states are called
        depending of the presence of states in stack.

        :param requires: A dict of requires name and values. Value is a list of dict of variable_name:value ::

            {req1 : [{variable1:value1,variable2:value2,...},{variable1:value3,variable2:value4,...},...],req2 ...}

        :rtype: list of (state,["entry"|"leave"])

        """
        path = self.get_state_path(state, go_back=go_back)
        if path == []:
            raise StateNotApply()
        for s in path:
            if s[1] == "entry":
                self._push_state(s[0], requires)
            elif s[1] == "leave":
                if self.get_current_state() == s[0]:
                    self._pop_state()
                else:
                    raise StateNotApply(self.get_current_state())

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
        for s in self.get_states():
            if s.name == state:
                return s
        raise StateNotExist("%s is not a valid state" % state)

    def get_state_path(self, state, fct=None, go_back=True):
        """From the current state, return the path to goto the state.
        If fct is not None, fct is applied on each state on the path.
        state arg is preprocessed by _get_state_class method. It then can be a str or a class.
        """
        state = self._get_state_class(state)
        logger.debug("get_state_path state '%s'" % state)
        r = self._get_from_state_path(self.get_current_state(), state, go_back=go_back)
        if fct != None:
            for state in r:
                fct(state[0])
        return r

    def get_state_requires(self, state, go_back=True):
        """Return all requires needed to go from current state to state."""
        acc = []
        for s in self.get_state_path(state, go_back=go_back):
            if s[1] == "entry":
                acc += s[0].get_requires()
        return acc

    def get_stack_provides(self):
        """:rtype: the list of states and provides for the current stack."""
        return [(s, s.get_provides()) for s in self._stack if s.get_provides() != []]

    def get_provides(self):
        """:rtype: the list of all states and provides."""
        return [(s, s.get_provides()) for s in self.get_states() if s.get_provides() != []]

    def _get_state_from_provide(self, provide_name):
        """From a provide_name, return a tuple of (state, provide_name).
        provide_name can be fully qualified, ie. state.provide_name."""
        p = provide_name.split(".")
        if len(p) == 1: # Simple provide name
            sp = []
            for (s, ps) in self.get_provides():
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

    def get_provide_requires(self, provide_name):
        """From a provide_name, return the list of "requires" needed to
        apply the state which provides provide_name."""
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            return self.get_state_requires(s)
        else:
            return []

    def get_provide_args(self, provide_name):
        """From a provide_name, returns its needed arguments."""
        (s, p) = self._get_state_from_provide(provide_name)
        return s.get_provide_args(p)

    def get_provide_path(self, provide_name):
        """From a provide_name, return the path to the state that
        provides the "provide"."""
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            return self.get_state_path(s)
        else:
            return []

    def call_provide(self, provide_name, requires, provide_args):
        """Call a provide and go to provider state if needed.

        :param provide_name: The name (simple or fully qualified) of the provide
        :param requires: Requires needed to reach the state that provides this provide.
                         See :py:meth:`Lifecycle.goto_state` for more informations
        :param provide_args: Args needed by this provide

        """
        (s, p) = self._get_state_from_provide(provide_name)
        if not self._is_state_in_stack(s):
            self.goto_state(s, requires)
        return self.call_provide_in_stack(s, p, provide_args)

    def call_provide_in_stack(self, state, provide_name, provide_args):
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
        for s in self.get_states():
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


class LifecycleNotExist(Exception):
    pass


class LifecycleManager(object):
    """This is the high level object. It permits to load module, know
    which modules are loaded and interact with loaded modules.

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
        return self.lf.keys()

    def load(self, lf_name=None):
        """If lf_name is not set, return a list of loaded LF."""
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
    def get_current_state(self, lf_name):
        return self.get_by_name(lf_name).get_current_state().name

    @expose
    def get_state_path(self, lf_name, state_name):
        return [(i[0].name, i[1]) for i in self.get_by_name(lf_name).get_state_path(state_name)]

    @expose
    def get_state_requires(self, lf_name, state_name):
        return self.get_by_name(lf_name).get_state_requires(state_name)

    @expose
    def goto_state(self, lf_name, state_name, requires={}):
        return self.get_by_name(lf_name).goto_state(state_name, requires)

    @expose
    def get_states(self, lf_name):
        return [s.name for s in self.get_by_name(lf_name).get_states()]

    @expose
    def get_provides(self, lf_name, in_stack=False):
        """If in_stack is True, just returns provides available in
        stack. Otherwise, returns all provides of this lf_name."""
        acc = {}
        if in_stack:
            ps = self.get_by_name(lf_name).get_stack_provides()
        else:
            ps = self.get_by_name(lf_name).get_provides()
        for (s, p) in ps:
            acc.update({s.name: [i.to_primitive() for i in p]})
        return acc

    @expose
    def get_provide_requires(self, lf_name, provide_name):
            return self.get_by_name(lf_name).get_provide_requires(provide_name)

    @expose
    def get_provide_args(self, lf_name, provide_name):
            return self.get_by_name(lf_name).get_provide_args(provide_name)

    @expose
    def get_provide_path(self, lf_name, provide_name):
        return [(s.name, a) for (s, a) in self.get_by_name(lf_name).get_provide_path(provide_name)]

    @expose
    def call_provide(self, lf_name, provide_name, requires={}, provide_args={}):
        print "ARGS" % provide_args
        return self.get_by_name(lf_name).call_provide(provide_name, requires, provide_args)

    @expose
    def to_dot(self, lf_name):
        return self.get_by_name(lf_name).to_dot()
