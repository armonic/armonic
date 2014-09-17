[![Build Status](https://travis-ci.org/armonic/armonic.png)](https://travis-ci.org/armonic/armonic)
Armonic
=======

Armonic is a deployment tool based on state machines. It's basically
composed by an agent and several kinds of client.

With Armonic, an sysadmin/devops can:
* build a distributed application by assembling predefined services,
* know what will happen on each node,
* use suggested configuration values,
* save deployments to play them again.

Installation
------------

Requirements are:
  
* setuptools:
  `apt-get install setuptools`

* lxml and python development librairies:
  `apt-get install python-lxml libpython-dev`

To install Armonic as a user: `python setup.py install --user`


Quick start guide
-----------------

In this quick start guide, we use the *local* version of Armonic which
doesn't require any agent.

### Basic usage

Then, you can begin to use Armonic by listing available modules so-called [*Lifecycle*](http://armonic.readthedocs.org/en/latest/lifecycle.html):

  `armonic-cli-local lifecycle`

We have implemented two dummy lifecycle:

* *WebServer* simulates a webserver service,
* *WebSite* simulates a website and depends of *WebServer*.

To activate the webserver run:

  `armonic-cli-local -v provide-call //WebServer//start`

`armonic-cli-local` tool is used to do basic task such as get informations about lifecycles, call simple provides, etc. For more informations about it, type `armonic-cli-local -h`.


### Orchestration

Basically, to deploy a website, we have to first create a document root on the webserver, and then install website files in this directory. These tasks can be orchestrated by the tool `smartonic`.

Let's try it:

`smartonic-cli-local //WebSite//start` 

Then, follow it and see messages which simulates the deployment of a website.

Full documentation
------------------

Documentation on http://armonic.readthedocs.org/en/latest/
