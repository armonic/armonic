.. _lifecycle:

Lifecycle anatomy
#################

:class:`Lifecycle` is an automaton with a set of :class:`State` and transitions between these
states.

The state machine represents differents steps (called states) for deploying a service. For
example the installation, the configuration, the activation of the service.

When a state is reached, it is added in a stack managed by :class:`Lifecycle`. This permits to
know which states have been applied in order to be able to unapplied them. This stack in internally
managed and thus not exposed.

State
=====

A :class:`State` describes the actions to do in a particular state of
a :class:`Lifecycle`. It can be actions when entering in the state or actions
available when the state is applied (in the stack).

States are pure python classes and actions are the methods of the class. The
actions are called provides. Methods must be decorated to be used as provides.

To create a state you just need to subclass :class:`State`::

    from armonic import State

    class MyState(State):
        pass

More about :ref:`state`.

Provide
=======

A :class:`Provide` describes a :class:`State` method of a :class:`Lifecycle`.
The :class:`Provide` defines the list of requires to be provided in order
to call a state method like it was arguments of the method.

For example a state provide (method) with no requires (arguments) can be declared
like this::

    from armonic import State

    class MyState(State):

        @Provide()
        def my_provide(self):
            # actions here
            pass

Each state has at least the :class:`Provide` ``enter``. This method is called
when entering the state.

To other methods are also reserved: ``leave`` and ``cross``. You can override
``leave`` if actions must be done when leaving the state. ``leave`` cannot take
any arguments. ``cross`` is used when the state is traversed.

Flags
-----

Flags can be defined on a :class:`Provide`. These flags are propagated to upper
states when the :class:`Provide` is called.

When a provide is called the state that contains the provide is applied (in the
:class:`Lifecycle` stack). It can be a state that is not the current state (ie
the last state applied). In that case the provide flags will be propagated to
the ``cross`` methods of each state that was applied after the provide's state.

See :ref:`flag`.

Require
=======

:class:`Require` describes the arguments needed to call a :class:`Provide`.
A require is a group of :class:`Variable` with some context (name, extra
information...)

Different of types of requires can be used:

* :class:`Require` defines arguments that should be provided.
* :class:`RequireLocal` defines that another :class:`Provide` must be called
  on *the same host* before. The result of this call can be used if needed.
* :class:`RequireExternal` defines that another :class:`Provide` must be called
  on *a different host* before. The result of this call can be used if needed.

More about :ref:`require`.

Variable
========

:class:`Variable` describes a :class:`Provide` argument with some context
(name, default value, optional, validation and more).

:class:`Variables` are grouped in :class:`Require`.

More about :ref:`variable`.
