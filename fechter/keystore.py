# Copyright 2011 Johan Rydberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import uuid

from twisted.internet import defer, task, error
from twisted.python import log
from txgossip.recipies import KeyStoreMixin, LeaderElectionMixin

from .assign import AssignmentComputer


class _LeaderElectionProtocol(LeaderElectionMixin):
    """Private version of the leader election protocol that informs
    the application logic about election results.
    """

    def __init__(self, clock, app):
        LeaderElectionMixin.__init__(self, clock, vote_delay=2)
        self._app = app

    def leader_elected(self, is_leader, leader):
        LeaderElectionMixin.leader_elected(self, is_leader, leader)
        self._app.leader_elected(is_leader)


class FechterProtocol:
    """Implementation of our 'fechter protocol'."""

    STATUS = 'private:status'

    def __init__(self, clock, storage, platform, pinger):
        self.election = _LeaderElectionProtocol(clock, self)
        self.keystore = KeyStoreMixin(clock, storage,
                [self.election.LEADER_KEY, self.election.VOTE_KEY,
                 self.election.PRIO_KEY, self.STATUS])
        self.computer = AssignmentComputer(self.keystore)
        self.platform = platform
        self.clock = clock
        self.pinger = pinger
        self._connectivity_checker = task.LoopingCall(
            self._check_connectivity)
        self._status = 'down'
        self._connectivity = 'down'

    @defer.inlineCallbacks
    def _check_connectivity(self):
        """Check connectivity with gateway."""
        tries = 0
        done = 0
        while not done:
            tries += 1
            try:
                yield self.pinger.check_connectivity(timeout=1)
            except error.TimeoutError:
                if tries == 3:
                    self.set_connectivity('down')
                    break
            else:
                done = 1
        else:
            self.set_connectivity('up')

    def _update_status(self):
        """Update status that will be communicated to other peers."""
        status = self._status if self._connectivity == 'up' else 'down'
        log.msg('change status to in keystore to "%s"' % (status,))
        self.gossiper.set(self.STATUS, status)

    def connectivity(self):
        """Return current connectivity status."""
        return self._connectivity

    def set_connectivity(self, status):
        """Change connectivity status.

        @param status: A string that is either C{up} or C{down}.
        @type status: C{str}
        """
        assert status in ('up', 'down')
        if status != self._connectivity:
            self._connectivity = status
            self._update_status()

    def status(self):
        """Return current administrative status."""
        return self._status

    def set_status(self, status):
        """Change status.

        @param status: A string that is either C{up} or C{down}.
        @type status: C{str}
        """
        assert status in ('up', 'down')
        if status != self._status:
            self._status = status
            self._update_status()

    def add_resource(self, resource):
        """Add a resource.

        @param resource: the resource that can be distributed over the
            cluster
        @type resource: a C{str}

        @return: the unique ID of the resource
        @rtype: C{str}
        """
        resource_id = str(uuid.uuid4())
        resource_key = 'resource:%s' % (resource_id,)
        self.keystore[resource_key] = [self.clock.seconds(),
            'please-assign', resource]
        return resource_id

    def list_resources(self):
        """Return a mapping of all existing resources."""
        resources = {}
        for key in self.keystore.keys('resource:*'):
            if self.keystore[key] is None:
                continue
            resource_id = key[9:]
            timestamp, state, resource = self.keystore[key]
            if state != 'please-assign':
                continue
            resources[resource_id] = {'resource': resource}
            assign_key = 'assign:%s' % (resource_id,)
            if assign_key in self.keystore:
                assigned_to = self.keystore[assign_key]
                if assigned_to:
                    resources[resource_id]['assigned_to'] = assigned_to
        return resources

    def _check_consensus(self, key):
        """Check if all peers have the same value for C{key}.

        Return the value if they all have the same value, otherwise
        return C{None}.
        """
        correct = self.gossiper.get(key)
        for peer in self.gossiper.live_peers:
            if not key in peer.keys():
                return None
            value = peer.get(key)
            if value != correct:
                return None
        return correct

    def value_changed(self, peer, key, value):
        """A peer changed one of its values."""
        if key == '__heartbeat__':
            return

        if self.election.value_changed(peer, key, value):
            # This value change was handled by the leader election
            # protocol.
            return
        self.keystore.value_changed(peer, key, value)

        if key == self.STATUS:
            self.status_change(peer, value == 'up')
            return

        if peer.name != self.gossiper.name:
            # We ignore anything that has not yet been replicated to
            # our own peer.
            return

        if self.election.is_leader is None:
            # Ignore because we have not seen an election yet.
            return

        if key.startswith('assign:'):
             # First check if we want any resources at all, since this
             # may be an old assignment.
             status = self.gossiper.get(self.STATUS)
             resource_id = key[7:]
             resource_key = 'resource:%s' % (resource_id,)
             self.platform.assign_resource(resource_id,
                 self.keystore.get(key) == self.gossiper.name,
                 self.keystore.get(resource_key)[2])
        elif key.startswith('resource:'):
             if self.election.is_leader:
                 self.assign_resources()

    def status_change(self, peer, up):
        """A peer changed its status flag.

        @param up: true if the peer changed its status to I{up}.
        @type up: C{bool}
        """
        log.msg('status changed for %s to %s' % (peer.name,
            "up" if up else "down"))
        if self.election.is_leader:
            self.assign_resources()

    def leader_elected(self, is_leader):
        """The result of an election is in.

        @param is_leader: C{true} if this peer was elected thr
           leader of the cluste.r
        @type is_leader: C{bool}
        """
        log.msg('leader elected and it %s us!' % (
                "IS" if is_leader else "IS NOT"))
        if is_leader:
            self.assign_resources()

    def collect_peers(self):
        """Gather up which peers that should be assigned resources.

        Skip a peer if it is dead or if it has its C{status} falg set
        to something else than C{'up'}.
        """
        peers = [peer.name for peer in self.gossiper.live_peers
                 if peer.get(self.STATUS) == 'up']
        if self.gossiper.get(self.STATUS) == 'up':
            peers.append(self.gossiper.name)
        peers.sort(key=lambda peer: hash(peer))
        return peers

    def assign_resources(self):
        """Process and assign resources to peers in the cluster."""
        self.computer.assign_resources(self.collect_peers())

    def make_connection(self, gossiper):
        """Make connection to gossip instance."""
        self.gossiper = gossiper
        self._update_status()
        self.election.make_connection(gossiper)
        self.keystore.make_connection(gossiper)
        self._connectivity_checker.start(5)

    def peer_alive(self, peer):
        self.election.peer_alive(peer)

    def peer_dead(self, peer):
        self.election.peer_alive(peer)
