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
from unittest.mock import patch

from nectar_osc import show
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


class TestShow(test.TestCase):
    def _run(self, cls, argv):
        command = cls(Mock(), Mock())
        clients = command.app.client_manager
        clients.compute.get_server.side_effect = (
            fakes.make_fake_clients().compute.get_server
        )
        parsed_args = command.get_parser('show').parse_args(argv)
        out = self.capture_stdout()
        command.take_action(parsed_args)
        return command, out.getvalue()

    def test_get_parser(self):
        for cls in [show.ShowInstance, show.ShowSecuritygroups]:
            command = cls(Mock(), Mock())
            parser = command.get_parser('show')
            self.assertEqual('abc', parser.parse_args(['abc']).id)
            with self.assertRaises(SystemExit):
                parser.parse_args([])

    @patch('nectar_osc.show.compute.show_instance')
    def test_show_instance(self, mock_show):
        mock_show.return_value = 'INSTANCE DETAILS'
        command, output = self._run(
            show.ShowInstance, ['00000000-1111-1111-1111-111111111112']
        )
        clients = command.app.client_manager
        clients.compute.get_server.assert_called_once_with(
            '00000000-1111-1111-1111-111111111112'
        )
        mock_show.assert_called_once_with(
            clients, '00000000-1111-1111-1111-111111111112'
        )
        self.assertEqual('INSTANCE DETAILS\n', output)

    @patch('nectar_osc.show.network.show_instance_security_groups')
    def test_show_securitygroups(self, mock_show):
        mock_show.return_value = 'SECURITY GROUPS'
        command, output = self._run(
            show.ShowSecuritygroups, ['00000000-1111-1111-1111-111111111113']
        )
        clients = command.app.client_manager
        clients.compute.get_server.assert_called_once_with(
            '00000000-1111-1111-1111-111111111113'
        )
        mock_show.assert_called_once_with(
            clients, '00000000-1111-1111-1111-111111111113'
        )
        self.assertEqual('SECURITY GROUPS\n', output)
