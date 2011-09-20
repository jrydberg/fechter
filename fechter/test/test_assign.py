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

from mockito import mock, when, verify, verifyNoMoreInteractions

from twisted.trial import unittest

from fechter.assign import AssignmentComputer, _calculate_assignment


class CalculateAssignmentTestCase(unittest.TestCase):
    """Test cases for C{_calculate_assignment}."""

    def test_selects_the_peer_with_least_assignments(self):
        assignments = {'A': 'a', 'B': 'a', 'C': 'b'}
        peer = _calculate_assignment(assignments, ['a', 'b'])
        self.assertEquals(peer, 'b')

    def test_select_peer_in_order_when_theres_a_tie(self):
        assignments = {'A': 'a', 'B': 'a', 'C': 'b', 'D': 'b'}
        peer = _calculate_assignment(assignments, ['b', 'a'])
        self.assertEquals(peer, 'b')
        peer = _calculate_assignment(assignments, ['a', 'b'])
        self.assertEquals(peer, 'a')


class AssignmentComputerTestCase(unittest.TestCase):
    """Test cases for C{AssignmentComputer}"""

    def setUp(self):
        self.keystore = mock()
        self.computer = AssignmentComputer(self.keystore)

    def test_collect_assignments_collects_assignments(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        when(self.keystore).get('assign:A').thenReturn('a')
        assignments = self.computer.collect_assignments(['A'], ['a'])
        self.assertEquals(len(assignments), 1)
        self.assertIn('A', assignments)
        self.assertEquals(assignments['A'], 'a')

    def test_collect_assignments_ignore_irrelevant_assignments(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        assignments = self.computer.collect_assignments([], [])
        self.assertFalse(assignments)

    def test_collect_assignments_ignore_assignments_to_dead_peers(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        when(self.keystore).get('assign:A').thenReturn('a')
        assignments = self.computer.collect_assignments(['A'], [])
        self.assertFalse(assignments)

    def test_collect_assignments_ignore_old_assignments(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        when(self.keystore).get('assign:A').thenReturn(None)
        assignments = self.computer.collect_assignments(['A'], ['a'])
        self.assertFalse(assignments)

    def test_collect_resources_ignore_old_resources(self):
        when(self.keystore).keys('resource:*').thenReturn(['resource:A'])
        when(self.keystore).get('resource:A').thenReturn(None)
        resources = self.computer.collect_resources()
        self.assertEquals(resources, [])

    def test_collect_resources_ingore_deleted_resources(self):
        when(self.keystore).keys('resource:*').thenReturn(['resource:A'])
        when(self.keystore).get('resource:A').thenReturn(
            (0, 'please-do-not-assign', 'address'))
        resources = self.computer.collect_resources()
        self.assertEquals(resources, [])

    def test_collect_resources_sorts_according_to_timestamp(self):
        when(self.keystore).keys('resource:*').thenReturn(['resource:A',
                                                           'resource:B'])
        when(self.keystore).get('resource:A').thenReturn(
            (1, 'please-assign', 'address'))
        when(self.keystore).get('resource:B').thenReturn(
            (0, 'please-assign', 'address'))
        resources = self.computer.collect_resources()
        self.assertEquals(resources, ['B', 'A'])

    def test_compute_assignments_keeps_existing_assignments(self):
        assignments = self.computer.compute_assignments(
            ['A'], {'A': 'a'}, ['b', 'a'])
        self.assertEquals(assignments['A'], 'a')

    def test_compute_assignments_compute_new_assignments(self):
        assignments = self.computer.compute_assignments(
            ['A', 'B'], {}, ['b', 'a'])
        self.assertEquals(assignments['A'], 'b')
        self.assertEquals(assignments['B'], 'a')

    def test_update_assignments_deletes_old_assignemnts(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        self.computer.update_assignments({'B': 'b'})
        verify(self.keystore).set('assign:A', None)

    def test_update_assignments_creates_new_assigment(self):
        when(self.keystore).keys('assign:*').thenReturn([])
        self.computer.update_assignments({'B': 'b'})
        verify(self.keystore).set('assign:B', 'b')

    def test_assign_resources_leaves_current_assignment_state(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        when(self.keystore).get('assign:A').thenReturn('a')
        when(self.keystore).keys('resource:*').thenReturn(['resource:A'])
        when(self.keystore).get('resource:A').thenReturn(
            (0, 'please-assign', 'address'))
        self.computer.assign_resources(['a'])
        verify(self.keystore).keys('assign:*')
        verify(self.keystore).get('assign:A')
        verify(self.keystore).keys('resource:*')
        verify(self.keystore).get('resource:A')
        verifyNoMoreInteractions(self.keystore)

    def test_assign_resources_updates_assignments(self):
        when(self.keystore).keys('assign:*').thenReturn(['assign:A'])
        when(self.keystore).get('assign:A').thenReturn('a')
        when(self.keystore).keys('resource:*').thenReturn(['resource:A'])
        when(self.keystore).get('resource:A').thenReturn(
            (0, 'please-assign', 'address'))
        self.computer.assign_resources(['b'])
        verify(self.keystore).set('assign:A', 'b')
