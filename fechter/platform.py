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

"""System specific functionality for installing resources."""

import struct
import socket

from twisted.python import log
from twisted.internet import utils, defer


ETH_BROADCAST = 'ff:ff:ff:ff:ff:ff'
ETH_TYPE_ARP = 0x0806


class AbstractPlatform(object):
    """Base class for platform implementations."""

    def __init__(self):
        self._assigned_resources = {}

    def assign_resource(self, resource_id, assign_to_me, resource):
        """Possible assign a resource to this platform."""
        if assign_to_me:
            if resource_id not in self._assigned_resources:
                self._assigned_resources[resource_id] = resource
                self._install_resource(resource)
        else:
            if resource_id in self._assigned_resources:
                del self._assigned_resources[resource_id]
                self._release_resource(resource)

    def _install_resource(self, resource):
        """Install resource."""
        raise NotImplementedError("install_resource")

    def _release_resource(self, resource):
        """Release resource."""
        raise NotImplementedError("release_resource")


def ether_aton(addr):
    """Convert a ethernet address in form AA:BB:... to a sequence of
    bytes.
    """
    return ''.join([struct.pack("B", int(nn, 16))
                    for nn in addr.split(':')])


def _send_arp(ifname, address):
    """Send out a gratuitous on interface C{ifname}."""
    # Try to get hold of a socket:
    try:
        ether_socket = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        ether_socket.bind((ifname, ETH_TYPE_ARP))
        ether_addr = ether_socket.getsockname()[4]
    except socket.error, (errno, msg):
        if errno == 1:
            log.msg('ARP messages can only be sent by root')
            return
        raise
    # From Wikipedia:
    #
    # ARP may also be used as a simple announcement protocol. This is
    # useful for updating other hosts' mapping of a hardware address
    # when the sender's IP address or MAC address has changed. Such an
    # announcement, also called a gratuitous ARP message, is usually
    # broadcast as an ARP request containing the sender's protocol
    # address (SPA) in the target field (TPA=SPA), with the target
    # hardware address (THA) set to zero. An alternative is to
    # broadcast an ARP reply with the sender's hardware and protocol
    # addresses (SHA and SPA) duplicated in the target fields
    # (TPA=SPA, THA=SHA).
    gratuitous_arp = [
        # HTYPE
        struct.pack("!h", 1),
        # PTYPE (IPv4)
        struct.pack("!h", 0x0800),
        # HLEN
        struct.pack("!B", 6),
        # PLEN
        struct.pack("!B", 4),
        # OPER (reply)
        struct.pack("!h", 2),
        # SHA
        ether_addr,
        # SPA
        socket.inet_aton(address),
        # THA
        ether_addr,
        # TPA
        socket.inet_aton(address)
        ]
    ether_frame = [
        # Destination address:
        ether_aton(ETH_BROADCAST),
        # Source address:
        ether_addr,
        # Protocol
        struct.pack("!h", ETH_TYPE_ARP),
        # Data
        ''.join(gratuitous_arp)
        ]
    ether_socket.send(''.join(ether_frame))
    ether_socket.close()


class LinuxPlatform(AbstractPlatform):
    """GNU/Linux platform."""

    def __init__(self, sbin_ip='/sbin/ip'):
        AbstractPlatform.__init__(self)
        self.sbin_ip = sbin_ip

    @defer.inlineCallbacks
    def _install_resource(self, resource):
        """Install resource."""
        ifname, address = resource.split(':', 1)
        yield utils.getProcessOutput(self.sbin_ip, ['addr', 'add',
                str('%s/32' % (address)), 'dev', str(ifname)])
        _send_arp(ifname, address)

    def _release_resource(self, resource):
        """Release resource."""
        ifname, address = resource.split(':', 1)
        utils.getProcessOutput(self.sbin_ip, ['addr', 'del',
                str('%s/32' % (address)),
                'dev', str(ifname)]).addErrback(log.err)
