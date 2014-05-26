.. _xpath:


Armonic XPath
#############

XPath (XML Path Language) is a query language for selecting nodes from
an XML document. In Armonic, we use it to select resources, ie. such
as lifecycles, states, provides, requires and variables. These resources
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

XPath permits to address one or several resources in a generic and
standardized way. For instance, we can list all states of the
lifecycle `Webserver` with the command::

  $ armonic-cli state "//WebServer/*"

The XPath `"//WebServer/*"` matches all states of resource WebServer which is a lifecycle. To get states of all lifecycles::

  $ armonic-cli state "/*/*"


To get description of provide start of state Active::
  
  $ armonic-cli provide "/*/WebServer/Active/start" -l

Absolute XPath
--------------

A absolute XPath is a XPath that contains locations also called
LifecycleManager. They start with a `/`. To query the Armonic API,
Absolute XPath MUST be used. To avoid locations specification (which
can be redundant with the agent address), you can use a prefix such as
`//` or `/*/`.


Relative XPath
--------------

A relative XPath is a XPath that doesn't start with a `/`. They are
used to describe Armonic resources independently of the location
where they are loaded. Relative XPath are only used by the internal
API and they don't concern end users.


Armonic resource URI
====================

Since Armonic resources are modelized by a tree, we use the path to
provide unique resource identifier. Some methods of the API needs of
resource URI to avoid potential conflict. For instance, to reach a
state, we have to use a URI instead of a more generic XPath
(`state-goto` needs a XPath URI). 

A XPath URI is just a XPath that matches only one resource. To be sure
to provide an URI, use full specialized XPath, ie. don't use
wildcards, `//`, etc.
