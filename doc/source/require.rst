.. _require:

.. module:: armonic.require

Requires
########

Require
=======

Example with :class:`Require`:

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

Example with :class:`RequireLocal`:

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
