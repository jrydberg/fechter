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


from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.internet import reactor
import shelve

from fechter import service



class Options(usage.Options):

    longdesc = """High availability manager that can be used to move
distribute IP addresses over a cluster.
"""

    optParameters = (
        ("port", "p", 4573, "The port number to listen on."),
        ("listen-address", "a", None, "The listen address."),
        ("dateway", "g", None, "Gateway to check connecticity with"),
        ("data-file", "d", "fechter.data", "File to store data in."),
        ("attach", "s", None, "Address to running Fechter instance."),
        ("dead-at", "D", "8", "Treat peers when PHI larger than this")
        )


class MyServiceMaker(object):
    implements(IServiceMaker, IPlugin)

    tapname = "fechter"
    description = "high availaibility manager"
    options = Options

    def makeService(self, options):
        """."""
        if not options['listen-address']:
            raise usage.UsageError("listen address must be specified")
        s = service.Fechter(
            reactor, options['listen-address'], int(options['port']),
            shelve.open(options['data-file'], writeback=True),
            phi=int(options['dead-at']))
        if options['attach']:
            s.gossiper.seed([options['attach']])
        return s

serviceMaker = MyServiceMaker()
