.. _flag:

Flags usage
###########

Given the following :class:`armonic.lifecycle.Lifecycle`:

.. code-block:: python
    :emphasize-lines: 5,10

    from armonic import Lifecycle, Transition, State, Flags

    class StateA(State):

        @Flags(reload=True)
        def provide1(self):
            # do stuff
            pass

        @Flags(restart=True)
        def provide2(self):
            # do other stuff
            pass

    class StateB(State):

        def cross(self, reload=False, restart=False):
            if reload:
                # do stuff
                pass
            if restart:
                # do stuff
                pass

    class LifecycleA(Lifecycle):
        initial_state = StateA()
        transitions = [Transition(StateA(), StateB())]

    lf = LifecycleA()
    lf.state_goto('//StateB')
    ret = lf.provide_call('//provide1')
    # StateB.cross called with reload=True
    ret = lf.provide_call('//provide2')
    # StateB.cross called with restart=True

If the current state of :class:`LifecycleA` is :class:`StateB` and we call
:meth:`provide1`, :meth:`StateB.cross` will be called with ``reload=True``
after that :meth:`provide1` returns. If :meth:`provide2` is called,
:meth:`StateB.cross` will be called with ``restart=True``.
