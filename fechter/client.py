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

VERSION = '0.0'

from optparse import OptionParser
import json
import sys
import httplib


class Agent:
    """Wrapper around httplib.

    @ivar connection: a L{httplib.HTTPConnection} to the remote
        server.
    """
    _VERSIONS = {10: 'HTTP/1.0', 11: 'HTTP/1.1'}

    def __init__(self, do_dump, *args):
        self.do_dump = do_dump
        self.connection = httplib.HTTPConnection(*args)

    def request(self, method, uri, data=None, headers=None):
        """Send a request and read out the response.

        @return: response object
        """
        if headers is None:
            headers = {}
        self.connection.request(method, uri, data, headers)
        return self.connection.getresponse()

    def _dumpnl(self, s):
        print >>sys.stderr, s

    def _dump_request_line(self, direction, method, uri):
        self._dumpnl('%s: %s %s HTTP/1.1' % (direction, method, uri))

    def _dump_response_line(self, direction, version, status, reason):
        self._dumpnl('%s: %s %s %s' % (direction, self._VERSIONS[version],
                                       status, reason))

    def _dump_header(self, direction, key, value):
        key = '-'.join((ck.capitalize() for ck in key.split('-')))
        self._dumpnl('%s: %s: %s' % (direction, key, value))

    def _dump_header_text(self, direction, lines):
        for line in lines.split('\r\n'):
            self._dumpnl('%s: %s' % (direction, line))

    def _dump_text(self, direction, lines):
        for line in lines.split('\n'):
            self._dumpnl('%s: %s' % (direction, line))

    def _dump_data(self, direction, data):
        for line in data.split('\n'):
            self._dumpnl('%s: %s' % (direction, line))

    def interact(self, uri, data=None, method="GET", headers=None):
        """Interact with the remote server.

        @param uri: uri of the remote resource
        @param data: possible data to send to the resource
        @type data: C{dict}
        @param method: http method
        @type method: C{str}
        """
        if headers is None:
            headers = {}
        headers['Accept'] = 'application/json'

        if isinstance(data, dict):
            data = json.dumps(data)
            headers['Content-Type'] = 'application/json'
        else:
            headers['Content-Type'] = 'text/plain'

        if data is not None:
            if self.do_dump:
                self._dump_request_line('C', method, uri)
                for key, value in headers.items():
                    self._dump_header('C', key, value)
                self._dumpnl('C:')
                self._dump_data('C', data)
            response = self.request(method, uri, data=data, headers=headers)
        else:
            if self.do_dump:
                self._dump_request_line('C', method, uri)
                for key, value in headers.items():
                    self._dump_header('C', key, value)
                self._dumpnl('C:')
            response = self.request(method, uri, headers=headers)
        if self.do_dump:
            self._dump_response_line('S', response.version,
                response.status, response.reason)
            for key, value in response.getheaders():
                self._dump_header('S', key, value)
            self._dumpnl('S:')
        if response.status in (httplib.OK, httplib.CREATED,
                               httplib.ACCEPTED):
            response_content = response.read()
            # FIXME: parse data
            data = response_content
            if self.do_dump:
                self._dump_data('S', data)
            return data
        elif response.status in (httplib.NO_CONTENT,):
            response_content = response.read()
            return None
        else:
            response_content = response.read()
            if response_content:
                try:
                    response_data = json.loads(response_content)
                except ValueError:
                    response_data = None
            else:
                response_data = None
            if self.do_dump and response_data is not None:
                self._dump_data('S', response_data)
            raise Exception(response.status, data=response_data)


class FechterClient(object):
    """Functionality for communicating with a Fechter service."""

    def __init__(self, agent):
        self.agent = agent

    def add_address(self, address):
        return self.agent.interact('/resource', data=address,
            method='POST')

    def set_status(self, status):
        return self.agent.interact('/status', data=status, method='POST')

    def resources(self):
        """Return a mapping for all resources."""
        return json.loads(self.agent.interact('/resource'))

    def info(self):
        """Return a bit of information about the cluster."""
        return json.loads(self.agent.interact('/info'))


def _usage():
    sys.exit("usage: fechter [options] COMMAND [options]")


def _add_address(client, args):
    if len(args) != 1:
        sys.exit("usage: fechter add-address IFNAME:ADDRESS")
    # Validate the format:
    try:
        ifname, address = args[0].split(':', 1)
        socket.inet_aton(address)
    except ValueError:
        sys.exit("error: invalid resource format")
    except socket.error:
        sys.exit("error: not a valid IPv4 address")
    client.add_address(args[0])


def _up(client, args):
    if len(args) != 0:
        sys.exit("usage: fechter up")
    client.set_status('up')


def _down(client, args):
    if len(args) != 0:
        sys.exit("usage: fechter down")
    client.set_status('down')


def _split_host_port(hostport):
    host, port = hostport.split(':', 1)
    return host, int(port)


import socket


def _info(client, args):
    """Display some information about the cluster."""
    parser = OptionParser(version="%%prog %s" % VERSION, prog="fechter",
        usage='fechter [options] status [options]')
    parser.add_option('-n', '--no-resolve', dest="no_resolve",
                      action="store_true", default=False,
                      help="Do not resolve names")
    (options, args) = parser.parse_args(args=args)
    info = client.info()
    for hostname, data in info['neighborhood'].items():
        if not options.no_resolve:
            host, port = _split_host_port(hostname)
            try:
                hostname = socket.gethostbyaddr(host)[0]
            except socket.error:
                hostname = host
        print "%s is %s" % (hostname,
            "alive" if data['alive'] else "dead")


def _status(client, args):
    """Display some status about the resources."""
    parser = OptionParser(version="%%prog %s" % VERSION, prog="fechter",
        usage='fechter [options] status [options]')
    parser.add_option('-n', '--no-resolve', dest="no_resolve",
                      action="store_true", default=False,
                      help="Do not resolve names")
    (options, args) = parser.parse_args(args=args)
    resources = client.resources()
    for resource_id, resource in resources.items():
        if not 'assigned_to' in resource:
            print "%s is not assigned" % (
                resource['resource'])
        else:
            if options.no_resolve:
                hostname = resource['assigned_to']
            else:
                host, port = _split_host_port(
                    resource['assigned_to'])
                try:
                    hostname = socket.gethostbyaddr(
                        host)[0]
                except socket.error:
                    hostname = host
            print "%s assigned to %s" % (
                resource['resource'], hostname)


def main(args):
    """."""
    parser = OptionParser(version="%%prog %s" % VERSION, prog="fechter",
        usage='fechter [options] COMMAND [options]')
    parser.disable_interspersed_args()
    parser.add_option('-D', '--dump', dest="dump",
                      action="store_true", default=False,
                      help="Dump communicaiton between S and C")
    parser.add_option('-v', '--verbose', dest="verbose",
                      action="store_true", default=False,
                      help="Verbose messages while processing")
    parser.add_option('-H', '--host', dest="host", default='localhost',
                      help="host where fechter is running",
                      metavar="HOST")
    parser.add_option('-p', '--port', dest="port", type=int, default=4573,
                      help="port where fechter is running",
                      metavar="PORT")
    (options, args) = parser.parse_args(args=args)

    if len(args) == 0:
        _usage()
    if args[0] == 'add-address':
        command = _add_address
    elif args[0] == 'up':
        command = _up
    elif args[0] == 'down':
        command = _down
    elif args[0] == 'status':
        command = _status
    elif args[0] == 'info':
        command = _info
    else:
        sys.exit("error: unknown command")

    client = FechterClient(Agent(options.dump, options.host,
        options.port))
    command(client, args[1:])
