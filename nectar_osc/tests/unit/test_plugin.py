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

import unittest
from unittest.mock import Mock, patch
from nectar_osc import plugin


class TestPlugin(unittest.TestCase):
    def test_default_api_version(self):
        self.assertEqual(plugin.DEFAULT_API_VERSION, '1')

    def test_api_name(self):
        self.assertEqual(plugin.API_NAME, 'nectar')

    def test_api_version_option(self):
        self.assertEqual(plugin.API_VERSION_OPTION, 'nectar')

    def test_api_versions(self):
        self.assertIn('1', plugin.API_VERSIONS)
        self.assertEqual(
            plugin.API_VERSIONS['1'], 'nectar_osc.v1.client.Client'
        )

    def test_make_client(self):
        client = plugin.make_client(Mock())
        self.assertIsNone(client)

    @patch('argparse.ArgumentParser')
    def test_build_option_parser(self, mock_parser):
        parser = plugin.build_option_parser(mock_parser)
        self.assertEqual(parser, mock_parser)
