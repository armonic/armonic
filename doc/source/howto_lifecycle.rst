Write a simple service Lifecycle
================================

We can say that a standard service has usually 4 states:

* Not installed: the packages of the service are not installed
* Installed: the packages of the service are installed
* Configured: the service is configured with configuration files, DB values
* Active: the service is running and is accepting requests

Using already provided States we can express a service Lifecycle easily. For
example we create the Lifecycle of the sshd service on a Debian like system::


    from armonic import Lifecycle, State, Transition
    from armonic.states import InitialState, InstallPackagesApt, ActiveWithSystemV


    class NotInstalled(InitialState):
        pass


    class Installed(InstallPackagesApt):
        packages = ['openssh-server']


    class Configured(State):

        def enter(self):
            with open('/etc/ssh/sshd_config', 'a') as f:
                f.write('AllowUsers admin')


    class Active(ActiveWithSystemV):
        services = ['sshd']


    class SSHServer(Lifecycle):
        initial_state = NotInstalled()
        transitions = [
            Transition(NotInstalled(), Installed()),
            Transition(Installed(), Configured()),
            Transition(Configured(), Active())
        ]

In this example we define 4 States for the service. The service Lifecycle
defines the possible transitions between the States. In this case the Lifecycle
transitions are very simple. From the :class:`NotInstalled` state can go to
:class:`Installed` state then to the :class:`Configured` state and finally
to the :class:`Active` state.

The :class:`Configured` state defines an enter method. This method is trigered when
entering the State (ie: when going from state :class:`Installed` to state :class:`Configured`).
In this example it will add a line to the ``/etc/ssh/sshd_config`` file to
restrict ssh connections to the ``admin`` user.

States like :class:`Installed` or :class:`Active` uses already provided States by
Armonic with standard python inheritance.
The :class:`InstallPackagesApt` state will make sure the package ``openssh-server``
is installed using Debian package management tools. The :class:`ActiveWithSystemV`
state will verify that the ``sshd`` service is running using the classic SystemV
init system.

Requires
--------

What if we wanted to provide manually configuration values to the service.
Using the :class:`Require` decorator you can define variables that need to be provided
to enter a State. Lets rewrite the :class:`Configured` state to take a users list to be
configured in the ``AllowUsers`` directive:

.. code-block:: python
    :emphasize-lines: 7,8

    from armonic import State, Require
    from armonic.variable import VList, VString


    class Configured(State):

        @Require('allowed_users', [VList('users', VString, default=["admin"], required=True)])
        def enter(self, requires):
            users = " ".join(requires.allowed_users.variables().users.values)
            with open('/etc/ssh/sshd_config', 'a') as f:
                f.write('AllowUsers %s' % users)

We define that to enter in the :class:`Configured` state we need to provide
a list of users in the ``allowed_users`` :class:`Require`. The list is named
``users`` and is composed of strings. This :class:`Require` cannot be empty
(``required=True``) and has a default value (``default=["admin"]``).

.. note:: Since the ``enter`` method has now a require you need add
          ``requires`` to the ``enter`` arguments.

A :class:`Require` can be composed of multiple variables. In our case it is only
composed of a :class:`VList`.

Check the complete documentation about :ref:`require`.

Variables
---------

Variables of the :class:`Require` are also python classes provided by Armonic. This
allows to create our own variables with custom validation. For example we could
verify that each user provided in the list actually exist on the system. We can
do that by simply inherit the :class:`VString` class and override the validate method::

    from armonic.variable import VString
    from armonic.common import ValidationError
    from armonic.utils import grep


    class SystemUser(VString):

        def validate(self, value):
            if not grep('/etc/passwd', value):
                raise ValidationError("The user %s doesn't exists on the system" % value)
            return True

Then it would be sufficient to change the :class:`Require` declaration to have a custom
validation on the user list::

    @Require('allowed_users', [VList('users', SystemUser, default=["admin"], required=True)])

Armonic provides the following base Variable classes: :class:`VString`, :class:`VInt`,
:class:`VFloat`, :class:`VBool`, :class:`VList`.

Check the complete documentation about :ref:`variable`.
