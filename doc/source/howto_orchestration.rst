How to write modules ready for orchestration 
============================================

Replication
-----------

Some modules allow replication which improves performance or
brings fault tolerance. Different kinds of replications can be
encountered such as master-slave or master/master.

In the master/master case, there is no difference between instances at
runtime. Thus, they expose same API (require and provide). However,
they could require differents parameters at set up time. 

For instance, the first instance of a galera cluster must create the
cluster, all other will just connect to it. Once the cluster is built,
all instances are equivalent.


The problem that appears is that instances are different at set up
time and equivalent at runtime. Because they are equivalent at
runtime, we don't want to use different state or lifecycle to build
them. Then, we are using to different technique to solve this
problem. 

The first one consists of using the list of armonic_hosts, while the
second one consists of declarating a armonic_first_instance variables.


We suppose that replicated instance are always load balanced or
managed by a common entities. For instance, Galera is load balanced by
HaProxy.

Thus, to build a Galera cluster, we first have to build a haproxy load
balancer. 

armonic_hosts
~~~~~~~~~~~~~

Smartlib will build the list of all load balanced hosts. If a load
balanced instance declare a variable armonic_hosts, smartlib will
construct and provide this list to all instances.

With the armonic_host variable, the instance is then able to know if
it is the first one or not.

amronic_first_instance
~~~~~~~~~~~~~~~~~~~~~~

Another way to specify if a instance is the first one is to declare a
variable armonic_first_instance. The advantage of this one is that
this variable can be explicitly set at deploy time.
