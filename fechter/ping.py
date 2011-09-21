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

import array
import os
import struct
import sys
import socket

from twisted.internet import abstract, defer, error


ECHO = 8
ECHOREPLY = 0


def _in_cksum(packet):
    """Generates a checksum of a packet."""
    if len(packet) & 1:
        packet = packet + '\0'
    words = array.array('h', packet)
    csum = 0
    for word in words:
        csum += (word & 0xffff)
    hi = csum >> 16
    lo = csum & 0xffff
    csum = hi + lo
    csum = csum + (csum >> 16)
    return socket.htons((~csum) & 0xffff)


def _pack_icmp(packet_id, sequence_no, num_data_bytes):
    """Pack a ICMP ECHO package and return it."""
    checksum = 0
    header = struct.pack("!BBHHH", ECHO, 0, checksum, packet_id,
        sequence_no)

    data_bytes = []
    start_val = 0x42
    for i in range(start_val, start_val + num_data_bytes):
        data_bytes += [(i & 0xff)]
    data = bytes(data_bytes)

    checksum = _in_cksum(header + data)
    header = struct.pack("!BBHHH", ECHO, 0, checksum, packet_id,
        sequence_no)
    return header + data


def _unpack_icmp(packet):
    """Unpack a ICMP packet.

    @return: the packet ID and the sequence number
    """
    header = packet[20:28]
    (type, code, checksum, packet_id,
         seq_number) = struct.unpack("!BBHHH", header)
    return type, packet_id, seq_number


class Pinger(abstract.FileDescriptor):
    """Functionality for checking connectivity with a remote host.

    The connectivity check is done by sending a ICMP ECHO (aka a ping)
    and expecting a reply.
    """
    seqno = 0

    def __init__(self, reactor, socket, address):
        abstract.FileDescriptor.__init__(self, reactor)
        self._socket = socket
        self._reading = 0
        self._waiting = {}
        self._address = address

    def _timeout(self, seq_no):
        if seq_no in self._waiting:
            d = self._waiting.pop(seq_no)
            d.errback(error.TimeoutError())

    def check_connectivity(self, timeout=2):
        """Check connectivity with remote address.

        Will send a ICMP ECHO packet to the remote address and expects
        a reply.

        @return: a deferred that will be called with C{None} on
            success or with C{TimeoutError} if the address did not
            respond.
        """
        self.seqno += 1
        d = defer.Deferred()
        self._waiting[self.seqno] = d

        # Construct a ICMP ECHO package and send it to the address.
        packet_id = os.getpid() & 0xffff
        self._socket.sendto(_pack_icmp(packet_id, self.seqno, 55), (
                self._address, 1))
        if not self._reading:
            self._reading = 1
            self.startReading()

        self.reactor.callLater(timeout, self._timeout, self.seqno)
        return d

    def doRead(self):
        """Read from file descriptor."""
        data, address = self._socket.recvfrom(2048)
        packet_type, packet_id, seq_no = _unpack_icmp(data)
        if packet_type != ECHOREPLY:
            return
        if seq_no in self._waiting:
            d = self._waiting.pop(seq_no)
            d.callback(None)

    def fileno(self):
        """File Descriptor number for select()."""
        return self._socket.fileno()
