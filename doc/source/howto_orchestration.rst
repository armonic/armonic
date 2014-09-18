Write modules ready for orchestration
=====================================

Replication
-----------

Some modules allow replication which improves performance or
brings fault tolerance features. Different kinds of replications
can be encountered such as master/slave or master/master.

In the master/master case, there is no difference between instances at
runtime. Thus, they expose same API (require and provide).
However, they could require differents parameters at set up time.

For instance, the first instance of a Galera cluster must create the
cluster, all other will just connect to it. Once the cluster is built,
all instances are equivalent.

The problem that appears is that instances are different at set up
time and equivalent at runtime. Because they are equivalent at
runtime, we don't want to use different state or lifecycle to build
them.

This can be solved by using :class:`armonic.variable.ArmonicHosts` and
:class:`armonic.variable.ArmonicHost` variables.

We suppose that replicated instances are always load balanced or
managed by a common entity. For instance, Galera is load balanced by
HaProxy. Thus, to build a Galera cluster, we first have to build a HaProxy
load balancer. HaProxy will call X times the creation of Galera nodes.

ArmonicHost and ArmonicHosts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When building the deployment tree lib smart construct a list of all instances
in the case of a replication and it also know which is the current instance.

The setup method of each instance can require the instances list by declaring
the variable :class:`armonic.variable.ArmonicHosts` in its `Requires`. You can
also require the variable :class:`armonic.variable.ArmonicHost` to get the
address of the current instance.

Example::

    @Require('nodes', [
        ArmonicHost("current", label="Current instance"),
        ArmonicHosts("list", label="List of instances")
    ])
    def my_instance_setup_method(self, requires):
        nodes = requires.nodes.variables().list.value
        # eg: nodes = ["192.168.1.1", "192.168.1.2"]
        node = requires.nodes.variables().current.value
        # eg: node = "192.168.1.1"

With this complete list of instances and the current instance address
the setup method can fully configure the current node.
