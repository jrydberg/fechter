# Fechter #

Fechter is a simple high-availability solution.  Use it to distribute
a set of IP aliases over your machines.  For example, say that you
have two machines: `ws-1` and `ws-2`.  With Fechter you can simply add
two additional IPs `ext-ws-1` and `ext-ws-2` that will be shared
between `ws-1` and `ws-2` depending on their state.  If `ws-1` goes
down for some reason (mechanical errors, maintaince, ...) `ws-2` will
assume responsibility for both `ext-ws-1` and `ext-ws-2`.

Fechter tries to evenly spread out the IP aliases over all available
nodes in the cluster.

Fechter assumes that it talks to its cluster members over the same
connection that will expose the IP aliases.

Currently we do not ping the gateway to check connectivity.  This will
be implemented soon.

The tool is named after Aaron Fechter, the created of Whac-A-Mole.

Fechter draws inspiration from http://www.backhand.org/wackamole/

## Installation ##

Requirements:

 - Twisted
 - txgossip
 - `/sbin/ip`
 - `/usr/sbin/arping`

Do not install it on your system just yet.  It is recommended that you
install it in a virtual env for now:

    $ virtualenv env
    $ . env/bin/activate
    $ easy_install Twisted
    $ easy_install txgossip
    $ easy_install fechter

## Running ##

Really, for all this to work you should be running Fechter as root.
But you do that at your own risk right now.

Starting fechter:

    $ twistd fechter --listen-address 10.0.0.10 --gateway 10.0.0.1

fechter will continuously check connectivity with the given gateway,
using ICMP ECHO (aka ping).  If the gateway refuses to respond,
fechter will stop accepting resources.  This helps a bit against
split-break scenarios.

The connectivity can always be checked using `fechter connectivity`:

    $ fechter connectivity
    can talk to gateway

If you already have fechter running on a different machine, you can
simply attach to that cluster by starting with the `--attach`
parameter:

    $ twistd fechter --listen-address 10.0.0.11 --gateway 10.0.0.1 --attach 10.0.0.10

Initially the cluster will not have any IP addresses assigned.  To add
an address.  Fechter expect that the address can be assigned to `eth0`
on any of the nodes in the cluster.

    $ fechter add-address eth0:10.0.0.20

When all your services are up and running, inform fechter about it,
otherwise the node will never receive any resources.

    $ fechter up

Showing status:

    $ fechter status
    eth0:10.0.0.20 assigned to 10.0.0.10

Adding an additional address:

    $ fechter add-address eth0:10.0.0.21
    $ fechter status
    eth0:10.0.0.20 assigned to 10.0.0.10
    eth0:10.0.0.21 assigned to 10.0.0.11

If you now kill the second machine:

    $ fechter status
    eth0:10.0.0.20 assigned to 10.0.0.10
    eth0:10.0.0.21 assigned to 10.0.0.10


# How does it work #

Each node in the high availability cluster runs an instance of
Fechter.  The instances all talk with each other using a gossip
protocol provided by [https://github.com/jrydberg/txgossip](txgossip).

The instances elect a leader that will be responsible for distributing
resources throughout the cluster.  A new election starts when a node
leaves or arrives at the cluster.

Each node does a connectivity check to make sure that it is able to
reach its gateway.  If it fails to do so, it will signal to the leader
that "i do not want any resources".

Future stuff:

The leader will constantly monitor the nodes in the instances by
sending them a "are you there?" message and expecting a reply.  If the
node does not answer, the resources allocated to that node will be
re-allocated to another node.

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

Currently existing assignments are not considered when a node in the
cluster changes it status.  This means that when a node goes up or
down (using `fechter down` for example) addresses gets redistributed.

For the same reasons, when an address is removed from the
configuration it is marked as "do-not-assign" instead of removed from
the list of addresses.

Addresses are installed on the node using `/sbin/ip`.  When an address
has been installed the `arping` tool is used to send out a gratuitous
ARP.
