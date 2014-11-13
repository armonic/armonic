%[![Build Status](https://travis-ci.org/armonic/armonic.png)](https://travis-ci.org/armonic/armonic)
Armonic
=======

Armonic is a deployment tool based on state machines. It's basically
composed by an agent and several kinds of clients.

With Armonic, an sysadmin/devops can:
* build a distributed application by assembling predefined services,
* know what will happen on each node,
* use suggested configuration values,
* save deployments to play them again.

Installation
------------

Requirements are:

* `apt-get install python-setuptools python-mysqldb python-lxml python-ipy python-netifaces python-prettytable python-nose python-augeas python-dev`

To install Armonic as a user: `python setup.py install --user`


Quick start guide
-----------------

In this quick start guide, we use the *local* version of Armonic which
doesn't require any agent.

### Basic usage

Then, you can begin to use Armonic by listing available modules so-called [*Lifecycle*](http://armonic.readthedocs.org/en/latest/lifecycle.html):

  `armocli-local lifecycle`

Two dummy lifecycle are available:

* *WebServer* simulates a webserver service,
* *WebSite* simulates a website and depends of *WebServer*.

For instance, to activate the webserver run:

  `armocli-local -v provide-call //WebServer//start`

`armocli-local` tool is used to do basic task such as get informations about lifecycles, call simple provides, etc. For more informations about it, type `armocli-local -h`.


### Orchestration

Basically, to deploy a website, we have to first create a document root on the webserver, and then install website files in this directory. These tasks can be orchestrated by the tool `smartonic`.

Let's try it:

`smartonic-local //WebSite//start`

Then, follow it and see messages which simulate deployment of a web site (and a web server).

Full documentation
------------------

Documentation on http://armonic.readthedocs.org/en/latest/
