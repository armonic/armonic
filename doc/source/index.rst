Armonic
#######

Armonic is a state machine system oriented for deployment written in python.

With Armonic you can express the different states of an application or a
service and make relations with other services. States can also provide
management methods to interact with the service.

Each `Lifecycle` (a state machine) representing an application or a service is
written in python. If you know already python it's really easy to get started
(See :ref:`lifecycle`).

Client tools are provided to interact with your collection of Lifecycles.

Architecture
============

.. image:: _images/armonic_archi.svg

Using CLI or Web frontends you can interact with the smart lib to manage the
deployment process. When a deployment is asked lib smart resolve the
deployment path across all concerned servers. Then the lib translate the
requirements to achieve the deployment to the frontend. The frontend fills
manually or automatically the requirements and then ask lib smart to orchestrate
the deployment.

Quickstart
==========

To enjoy the full potential of Armonic an XMPP server is needed. Multiple XMPP
servers are supported like Ejabberd or Prosody. The setup of Prosody is
described in this Quickstart.

Checking out the project
------------------------

Clone armonic from the github repository on your system. Create a python
virtualenv and install all the dependencies of Armonic without polluting your
system with the followind commands::

  git clone https://github.com/armonic/armonic.git
  cd armonic
  virtualenv --system-site-packages venv
  . venv/bin/activate
  python setup.py install

Prosody setup
-------------

On your favorite distribution install the `prosody` package. Then configure
a virtual host for Armonic in `/etc/prosody/prosody.cfg.lua`::

  VirtualHost "armonic.example.com"

In production you need to configure add an entry in your DNS server for
armonic.example.com with the IP of the prosody server, but you can also add
a line in your `/etc/hosts` file to test Armonic on your local machine.

To enable Armonic logs propagation between agents and clients the MUC module must
be enabled. Just add the following directive in the configuration::

  Component "logs.armonic.example.com" "muc"

Like the XMPP domain, configure your DNS server or /etc/hosts file.

This is all you need to use the armonic cli clients (`smartonic` and
`armocli`). To use the webinterface `warmonic` you also have to enable the
bosh and/or websocket modules. The Prosody websocket module can be found in the
prosody-modules project at https://code.google.com/p/prosody-modules/.

For the bosh and websocket modules use the following options::

  cross_domain_bosh = true;
  bosh_max_inactivity = 600;

  cross_domain_websocket = true;
  consider_websocket_secure = true;

For testing purposes you can enable the automatic creation of accounts so that
the agents running on the servers will register an account on the XMPP server
automatically::

  allow_registration = true;

Restart the Prosody service and you are good to go.

Setting up an admin account
---------------------------

On the XMPP server we need to create an account for the administrator. This
account will be used by the clients orchestrate the deployments::

  prosodyctl adduser master@armonic.example.com

Running the agents
------------------

If you have enable the automatic registration of accounts you can run the agent
directly. If not, create an account on the XMPP server for the agent.

Run the agent with::

  armonic-agent-xmpp --jid server_account@armonic.example.com --password server_password -v

The agent should be running and be connected to the XMPP server.

Using armocli
-----------------

`armocli` is the low level client for armonic. It allows you to call
armonic API methods directly. With this tool we can easily check any agent for
its status or available `Lifecyles` (Armonic modules) for example.

For exampe, run::

  armocli --jid master@armonic.example.com --password master_master list
  armocli --jid master@armonic.example.com --password master_master info -J server_account@armonic.example.com
  armocli --jid master@armonic.example.com --password master_master lifecycle -J server_account@armonic.example.com

Running deployments with smartonic
----------------------------------

smartonic is a client using lib smart allowing to contact multiple agents to
orchestrate a deployment. smartonic is used to call Armonic Provides aka
`States` methods. When calling a `Provide` smartonic will build the deployment
tree and will resolve any depedencies to complete the deployment. If some some
`Requires` are needed smartonic will prompt the user to fill some values.

Two tests modules are available to show how this works. They don't execute any
operation on the machine. Run the following
command::

  smartonic --jid master@armonic.example.com --password master_password --manage Website//start

The Website module emulates the configuration of a web application. This module
has a dependency on the Webserver module which emulates a webserver.

The Webserver dependency is first resolved and some configuration is needed to
setup the Webserver. `smartonic` will ask on wich port the Webserver will listen,
and where the document root will be setup. Some values are suggested and
validated when submitted. Then, the Webserver is deployed. After that some
configuration is needed on the Website module and finally the Website is
deployed.

Howto
#####

.. toctree::
   :maxdepth: 1

   howto_lifecycle
   howto_orchestration

Complete documentation
######################

.. toctree::
   :maxdepth: 2

   lifecycle
   components
   smart
   api
   running_modes

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
