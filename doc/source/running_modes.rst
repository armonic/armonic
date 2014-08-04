Running modes
=============

Several modes are available to use Armonic.


Simulation
----------

The SIMULATION flag inhibits body of provide method to be executed but
requires are validated and states are applied.

This is really useful to develop interaction between module without
applying any modification on the host.


Non validation on call
----------------------

With the simulation mode, a problem occurs with provide ret
values. Since we don't execute provides, Armonic provide methods don't
generate return values which are required to fill provide ret values.

We can set the flag armonic.common.DONT_VALIDATE_ON_CALL to avoid
these validation to occur on provide calls.


Don't call
----------

This mode is just useful for client since it inbits the client to
realize the provide call on the agent.
