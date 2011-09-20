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


def _calculate_assignment(assignments, peers):
    """Pick a peer that should receive the next assignment.

    @param assignments: Current assignments
    @type assigments: C{dict} where key is resource id, value is peer

    @param peers: sequence of alive peers that want to receive
        resources
    @type peers: sequence of C{str}
    """
    lengths = [len([pp for pp in assignments.values()
                    if pp == peer]) for peer in peers]
    suggestion = peers[lengths.index(min(lengths))]
    return suggestion


class AssignmentComputer(object):
    """Functionality that implements our assignment algorithm.

    The data model:

        The keystore holds key-value pairs.  Resources has the
        C{resource:} prefix.  Assignments has the C{assign:} prefix.

        Each resource has a unique random ID (a UUID normally) that
        identfiies the resource.  The value of the resource is a tuple
        of C{timestamp}, C{state} and C{address}.  C{timestamp} points
        out when in time the resource was created.  This is for
        sorting resources when computing the assignments.  C{state}
        can either be C{'please-assign'} or C{'please-do-not-assign'}.
        The C{address} field is an opaque string.
    """

    def __init__(self, keystore):
        self.keystore = keystore

    def compute_assignments(self, resources, current_assignments, peers):
        """Based on available resources, current assignments and
        available peers, compute assignments.

        @param resources: available resources that should be distributed
            over the peers
        @type resources: sequence of C{str}

        @param current_assignments: assignments to start the algorithm
            with
        @type current_assignments: C{dict} where key is resource id
            and value is the peer which the resource is assigned to

        @param peers: sequence of alive peers that want to receive
            resources
        @type peers: sequence of C{str}
        """
        assignments = current_assignments.copy()
        for resource_id in resources:
            if not resource_id in assignments:
                assignments[resource_id] = _calculate_assignment(
                    assignments, peers)
        return assignments

    def collect_resources(self):
        """Collect resources from our key-value store.

        @return: a sequence of resource ids, ordered by the time they
            were inserted into the keystore
        """
        resource_keys = self.keystore.keys('resource:*')
        resources = {}
        for resource_key in resource_keys:
            resource = self.keystore.get(resource_key)
            if resource is None:
                continue
            timestamp, state, address = resource
            if state != 'please-assign':
                continue
            resources[resource_key[9:]] = (address, timestamp)

        ordered_resources = sorted(resources.keys(),
             key=lambda k: resources[k][1])
        return ordered_resources

    def collect_assignments(self, resources, peers):
        """Go through the keystore and build up a mapping of
        the current assignment states.

        @param resources: sequence of known resources
        @type resources: sequence of C{str}

        @param peers: sequence of peers that is known to be alive and
            that accepts resources
        @type peers: sequence of C{str}

        @return: a mapping between resource name and assigned to peer.
        @rtype: C{dict}
        """
        assignments = {}
        for assign_key in self.keystore.keys('assign:*'):
            resource_id = assign_key[7:]
            if resource_id not in resources:
                continue
            assigned_to = self.keystore.get(assign_key)
            if assigned_to in peers and assigned_to is not None:
                assignments[resource_id] = assigned_to
        return assignments

    def update_assignments(self, assignments):
        """Update keystore with new assignments.

        This method will also kill any existing assignemnts in the
        keystore that is not mentioned in C{assignments}.
        """
        for assign_key in self.keystore.keys('assign:*'):
            resource_id = assign_key[7:]
            if resource_id not in assignments:
                self.keystore.set(assign_key, None)
        for resource_id, assign_to in assignments.items():
            assign_key = 'assign:%s' % (resource_id,)
            self.keystore.set(assign_key, assign_to)

    def assign_resources(self, peers):
        """Assign resources to the given peers.

        @param peers: alive peers that want to receive resources.
        @type peers: a sequence of C{str}
        """
        ordered_resources = self.collect_resources()
        current_assignments = self.collect_assignments(ordered_resources,
            peers)
        assignments = {}
        if peers:
            assignments = self.compute_assignments(ordered_resources,
                assignments, peers)
        if assignments != current_assignments or not assignments:
            self.update_assignments(assignments)

