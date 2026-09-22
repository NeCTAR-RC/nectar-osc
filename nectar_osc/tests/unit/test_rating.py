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

from unittest.mock import Mock

from nectar_osc import rating
from nectar_osc.tests import test


class FakeFlavor:
    def __init__(self, id, name):
        self.id = id
        self.name = name


FLAVORS = [
    FakeFlavor('f-1', 'm1.small'),
    FakeFlavor('f-2', 'm1.medium'),
    FakeFlavor('f-3', 'm1.unrated'),
]

GROUPS = [
    {'name': 'something_else', 'group_id': 'g-0'},
    {'name': 'instance_uptime_flavor_id', 'group_id': 'g-1'},
    {'name': 'instance_uptime_flavor_id', 'group_id': 'g-duplicate'},
]

MAPPINGS = [
    {'value': 'f-1', 'cost': '1.0'},
    {'value': 'f-2', 'cost': '2.5'},
    {'value': 'f-gone', 'cost': '9.9'},
]


class TestListFlavors(test.TestCase):
    def _make_command(self, flavors=FLAVORS, groups=GROUPS, mappings=MAPPINGS):
        command = rating.ListFlavors(Mock(), Mock())
        clients = command.app.client_manager
        clients.compute.flavors.return_value = flavors
        hashmap = clients.rating.rating.hashmap
        hashmap.get_group.return_value = {'groups': groups}
        hashmap.get_group_mappings.return_value = {'mappings': mappings}
        return command

    def _take_action(self, command, argv):
        parsed_args = command.get_parser('flavor list').parse_args(argv)
        columns, data = command.take_action(parsed_args)
        return columns, list(data)

    def test_get_parser(self):
        command = self._make_command()
        parser = command.get_parser('flavor list')
        self.assertFalse(parser.parse_args([]).all)
        self.assertTrue(parser.parse_args(['--all']).all)

    def test_list(self):
        command = self._make_command()
        columns, data = self._take_action(command, [])
        self.assertEqual(['id', 'name', 'rate'], columns)
        self.assertEqual(
            [
                ('f-1', 'm1.small', '1.0'),
                ('f-2', 'm1.medium', '2.5'),
                ('f-3', 'm1.unrated', None),
            ],
            data,
        )
        clients = command.app.client_manager
        clients.compute.flavors.assert_called_once_with()
        hashmap = clients.rating.rating.hashmap
        hashmap.get_group.assert_called_once_with()
        # The first matching group wins
        hashmap.get_group_mappings.assert_called_once_with(group_id='g-1')

    def test_list_all(self):
        """--all asks nova for the non-public flavors too"""
        command = self._make_command()
        self._take_action(command, ['--all'])
        clients = command.app.client_manager
        clients.compute.flavors.assert_called_once_with(is_public=None)

    def test_rate_added_to_flavor(self):
        command = self._make_command()
        self._take_action(command, [])
        self.assertEqual('1.0', FLAVORS[0].rate)
        self.assertEqual('2.5', FLAVORS[1].rate)
        self.assertIsNone(FLAVORS[2].rate)

    def test_no_rating_group(self):
        """Without the flavor rating group, all flavors are unrated"""
        command = self._make_command(
            groups=[{'name': 'something_else', 'group_id': 'g-0'}],
            mappings=[],
        )
        columns, data = self._take_action(command, [])
        hashmap = command.app.client_manager.rating.rating.hashmap
        hashmap.get_group_mappings.assert_called_once_with(group_id=None)
        self.assertEqual(
            [
                ('f-1', 'm1.small', None),
                ('f-2', 'm1.medium', None),
                ('f-3', 'm1.unrated', None),
            ],
            data,
        )

    def test_no_flavors(self):
        command = self._make_command(flavors=[])
        columns, data = self._take_action(command, [])
        self.assertEqual(['id', 'name', 'rate'], columns)
        self.assertEqual([], data)
