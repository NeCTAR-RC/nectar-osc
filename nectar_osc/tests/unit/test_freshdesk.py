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

from unittest.mock import patch

from oslo_config import cfg

from nectar_osc import freshdesk
from nectar_osc.tests import test


CONF = cfg.CONF


class TestFreshdesk(test.TestCase):
    def setUp(self):
        super().setUp()
        # get_client() (re)initialises the config from the user's
        # ~/.nectar-osc.conf; keep that away from the test environment.
        patcher = patch('nectar_osc.config.init')
        self.mock_init = patcher.start()
        self.addCleanup(patcher.stop)

    def _set(self, name, value):
        CONF.set_override(name, value, group='freshdesk')
        self.addCleanup(CONF.clear_override, name, group='freshdesk')

    def test_get_client_without_freshdesk_package(self):
        self._set('api_key', 'sekrit')
        out = self.capture_stdout()
        with patch('nectar_osc.freshdesk.api', None):
            with self.assertRaises(SystemExit) as cm:
                freshdesk.get_client()
        self.assertEqual(1, cm.exception.code)
        self.assertIn('pip install python-freshdesk', out.getvalue())
        # We bail out before even looking at the config
        self.mock_init.assert_not_called()

    def test_get_client_without_api_key(self):
        self._set('api_key', None)
        out = self.capture_stdout()
        with patch('nectar_osc.freshdesk.api') as mock_api:
            with self.assertRaises(SystemExit) as cm:
                freshdesk.get_client()
        self.assertEqual(1, cm.exception.code)
        self.mock_init.assert_called_once_with()
        mock_api.API.assert_not_called()
        self.assertIn(
            'No Freshdesk api key found in your config file.', out.getvalue()
        )
        self.assertIn(
            '[freshdesk]\n  api_key = <your api key>', out.getvalue()
        )

    def test_get_client(self):
        self._set('api_key', 'sekrit')
        self._set('domain', 'example.freshdesk.com')
        out = self.capture_stdout()
        with patch('nectar_osc.freshdesk.api') as mock_api:
            client = freshdesk.get_client()
        self.mock_init.assert_called_once_with()
        mock_api.API.assert_called_once_with('example.freshdesk.com', 'sekrit')
        self.assertIs(mock_api.API.return_value, client)
        self.assertEqual('', out.getvalue())

    def test_get_client_default_domain(self):
        self._set('api_key', 'sekrit')
        with patch('nectar_osc.freshdesk.api') as mock_api:
            freshdesk.get_client()
        mock_api.API.assert_called_once_with(
            'dhdnectar.freshdesk.com', 'sekrit'
        )
