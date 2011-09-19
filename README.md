# Fechter #

Fechter is a simple high-availability solution.

Fechter is modelled after http://www.backhand.org/wackamole/

## Running ##

Starting fechter:

    $ twistd fechter --listen-address 10.0.0.10 \
         --gateway 10.0.0.1

If you already have fechter running on a different machine, you can
simply attach to that cluster by starting with the `--attach`
parameter:

    $ twistd fechter --listen-address 10.0.0.11 \
         --gateway 10.0.0.1 --attach 10.0.0.10

Initially the cluster will not have any IP addresses assigned.  To add
an address.  Fechter expect that the address can be assigned to `eth0`
on any of the nodes in the cluster.

    $ fechter add-address eth0:10.0.0.20

When all your services are up and running, inform fechter about it,
otherwise the node will never receive any resources.

    $ fechter up

Showing status:

    $ fechter status
    10.0.0.20 assigned to 10.0.0.10

Adding an additional address:

    $ fechter add-address eth0:10.0.0.21
    $ fechter status
    10.0.0.20 assigned to 10.0.0.10
    10.0.0.21 assigned to 10.0.0.11

If you now kill the second machine:

    $ fechter status
    10.0.0.20 assigned to 10.0.0.10
    10.0.0.21 assigned to 10.0.0.10

If your local fechter instance thinks that it does not have any
connectivity:

    $ fechter connectivity
    error: cannot reach gateway

    $ fechter connectivity
    can reach gateway 10.0.0.1


# How does it work #

Each node in the high availability cluster runs an instance of
Fechter.  The instances all talk with each other using a gossip
protocol provided by (txgossip)[https://github.com/jrydberg/txgossip].

The instances elect a leader that will be responsible for distributing
resources throughout the cluster.  A new election starts when a node
leaves or arrives at the cluster.

The leader will constantly monitor the nodes in the instances by
sending them a "are you there?" message and expecting a retry.  If the
node does not answer, the resources allocated to that node will be
re-allocated to another node.

Each node does a connectivity check to make sure that it is able to
reach its gateway.  If it fails to do so, it will signal to the leader
that "i do not want any resources".

## The allocation algorithm ##

The resource allocation algorithm tries to spread addresses evenly
over all nodes in the cluster.

The algoritm is quite simple: allocate an address to the node that has
the least number of resources allocated.  If there are more than one
node with the same number of resources, pick the one with the lowest
hash value (the hash function is not defined here).  Do this until
there are no more addresses to distribute.

The addresses are distributed in the order that they were added to the
configuraiton, which means that all resources will not be reallocated
when a new address is added.

For the same reasons, when an address is removed from the
configuration it is marked as "do-not-assign" instead of removed from
the list of addresses.
