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


class LinuxPlatform(AbstractPlatform):
    """GNU/Linux platform."""

    def __init__(self, ip='/sbin/ip'):
        pass

    def assign_resource(self, resource_id, assign_to_me, resource):
        print "ASSIGN RESOURCE", resource_id, assign_to_me, resource

