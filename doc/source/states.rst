.. _states:

.. module:: mss.states

Predefined States
#################

Using a predefined state
========================

Usually you just need to subclass the state and adjust some class attributes.
Example with the :class:`InstallPackagesApt` class::

    from armonic.states import InstallPackagesApt

    class InstallOpenLDAP(InstallPackagesApt):
        packages = ["openldap-server"]

Include the :class:`InstallOpenLDAP` state in your Lifecycle transitions and you are done.

List of predefined states
=========================

Service activation
------------------

.. autoclass:: ActiveWithSystemd
   :members:

.. autoclass:: ActiveWithSystemV
   :members:

Package installation
--------------------

.. autoclass:: InstallPackagesApt
   :members:

.. autoclass:: InstallPackagesUrpm
   :members:
