.. _require:

Requires
########

A *require* allows user to specify values required to apply a state or
to call a provide. Basically, a *require* is used to specify a tuple
of values. These values are described by a list of
:class:`armonic.variable.Variable`.

The parameter `nargs` of a *require* is used to specify how many
times a require can be specified. For instance, a load balancer
requires several backend where each backend consists of a host and
port variable. The nargs parameters of the backend require of a load
balancer can be set to '*'.


Require
=======

Example with :class:`armonic.require.Require`:

.. code-block:: python
    :emphasize-lines: 3

    class ConfigureApache(State):

        @Require('ports', [VInt('http', default=80), VInt('https', default=443)])
        def set_ports(self, requires):
            print requires.ports.variables().http
            print requires.ports.variables().https

.. note::

    When calling the ``set_ports`` provide you can define port values for http
    and https. If no values are provided default values are used.

RequireLocal
============

Example with :class:`armonic.require.RequireLocal`:

.. code-block:: python
    :emphasize-lines: 3,4

    class ConfigureWordpress(State):

        @RequireLocal("dbinfo", "//Mysql//add_database",
                      provide_ret=[VString("dbname"), VString("dbuser"), VString("dbpassword")])
        def enter(self, requires):
            print requires.dbinfos.variables().dbname
            print requires.dbinfos.variables().dbuser
            print requires.dbinfos.variables().dbpassword

.. note::

    When entering the :class:`ConfigureWordpress` state the ``add_database`` provide will be
    called on the same system and the result of this call is saved in the ``requires``
    argument passed to the ``enter`` method. The provide to call is written with an
    xpath string.

RequireExternal
===============

:class:`armonic.require.RequireExternal` has the same usage as
:class:`armonic.require.RequireLocal`. The only difference is that a host must
be provided to :class:`armonic.require.RequireExternal`.
