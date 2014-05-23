.. _xpath:


Armonic XPath
#############

XPath (XML Path Language) is a query language for selecting nodes from
an XML document. In armonic, we use it to select resources, ie. such
as lifecycles, states, provides, requires and variables, since they
are modelized by a tree such as::


  Location (where lifecycles are loaded)
  |
  +--Webserver
  |  |
  |  +--NotInstalled (State)
  |  |  |
  |  |  +--enter (Provide)
  |  |
  |  +--Installed
  |  |  |
  |  |  +--enter
  |  |
  |  +--Configured
  |  |  |
  |  |  +--enter
  |  | 	|
  |  |	+--create_document_root
  |  |	   |
  |  |	   +--document_root (Variable of type str)
  |  |
  |  +--Active
  |     |
  |     +--enter
  |   	|
  |   	+--start
  |
  +--WebSite
  .  |
  .  .
  .  .
  .  .


XPath as selectors
==================

Xpath permits to adress one or several ressource in a generic and
standardized way. For instance, we can list all states of the
lifecycle `Webserver` with the command::

  $ armonic-cli state "//WebServer/*"

The XPath `"//WebServer/*"` matches all states of resource WebServer which is a lifecycle. To get states of all lifecycles::

  $ armonic-cli state "/*/*"

Absolute XPath
--------------

A absolute XPath is a XPath that contains locations also called
LifecycleManager. They start with a `/`.

Relative Xpath
--------------

A relative XPath is a XPath that doesn't start with a `/`. They are
used to describe Armonic ressource independantly of the location where
they are loaded.


Armonic resource URI
====================

Since Armonic resources are modelized by a tree, we use the path to
provide unique resource identifier. Some methods of the API needs of
resource URI to avoid potential conflict. For instance, to reach a
state, we have to use a URI instead of a more generic XPath.

