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

import uuid

from twisted.application import service
from twisted.web import server, http
from txgossip.gossip import Gossiper
from . import keystore, rest, platform, assign


class StatusController:
    """REST controller for the status of this node."""

    def __init__(self, gossiper):
        self.gossiper = gossiper

    def post(self, router, request, url, data):
        """Update status of the node."""
        if data in ('up', 'down'):
            self.gossiper.set('private:status', data)
            return http.OK
        return http.BAD_REQUEST

    def get(self, router, request, url):
        """Return current status of the node."""
        return self.gossiper.get('private:status')


class ResourceController:
    """REST controller for a single resource."""

    def __init__(self, clock, keystore):
        self.clock = clock
        self.keystore = keystore

    def delete(self, router, request, url, resource_id=None):
        key = 'resource:%s' % (resource_id,)
        if key not in self.keystore or self.keystore[key] is None:
            raise rest.NoSuchResourceError()
        self.keystore[key] = None
        return http.NO_CONTENT


class InfoController:
    """REST controller for info about the cluster."""

    def __init__(self, clock, gossiper):
        self.clock = clock
        self.gossiper = gossiper

    def get(self, router, request, url):
        """."""
        neighborhood = {}
        for peer in (self.gossiper.live_peers
                     + self.gossiper.dead_peers):
            neighborhood[peer.name] = {
                'alive': peer.alive,
                'phi': peer.detector.phi(
                    self.clock.seconds())
                }
        return {'neighborhood': neighborhood}


class ResourceCollectionController:
    """REST controller for the collection of all resources."""

    def __init__(self, clock, protocol):
        self.clock = clock
        self.protocol = protocol

    def get(self, router, request, url):
        """Return a mapping of all known resources."""
        return self.protocol.list_resources()

    def post(self, router, request, url, data):
        """Create a new resource."""
        if type(data) != str:
            return http.BAD_REQUEST
        resource_id = self.protocol.add_resource(data)
        return http.CREATED


class Fechter(service.Service):
    """High-availability service."""

    def __init__(self, reactor, listen_addr, listen_port, storage, phi=8):
        self.reactor = reactor
        self._listen_port = listen_port
        self.storage = storage
        self.platform = platform.LinuxPlatform()
        self.protocol = keystore.FechterProtocol(reactor, storage,
            self.platform)
        self.gossiper = Gossiper(reactor, self.protocol, listen_addr)

        self.router = rest.Router()
        self.router.addController('info', InfoController(
                self.reactor, self.gossiper))
        self.router.addController('resource/{resource_id}', ResourceController(
                self.reactor, self.protocol.keystore))
        self.router.addController('resource', ResourceCollectionController(
                self.reactor, self.protocol))
        self.router.addController('status', StatusController(
                self.gossiper))

    def startService(self):
        """Start the service."""
        self.reactor.listenUDP(self._listen_port, self.gossiper)
        self.reactor.listenTCP(self._listen_port, server.Site(
                self.router))
        # This is so ugly:
        self.gossiper.set(self.protocol.election.PRIO_KEY, 0)
        self.gossiper.set(self.protocol.STATUS, 'down')
        self.protocol.keystore.load_from(self.storage)
