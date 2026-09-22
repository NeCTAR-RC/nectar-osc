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

import os
import shutil
import tempfile
from unittest.mock import patch

from oslo_config import cfg

from nectar_osc import config
from nectar_osc.tests import test


CONF = cfg.CONF


class TestConfig(test.TestCase):
    def setUp(self):
        super().setUp()
        # Every test here (re)initialises the global CONF from some
        # config file; put the test configuration back afterwards.
        self.addCleanup(config.init, test.filename)
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def test_list_opts(self):
        opts = config.list_opts()
        self.assertEqual(
            ['freshdesk', 'mailout', 'nova'], [group for group, _ in opts]
        )
        by_group = dict(opts)
        self.assertEqual(
            ['api_key', 'email_config_id', 'group_id', 'domain'],
            [opt.name for opt in by_group['freshdesk']],
        )
        self.assertEqual(
            ['work_dir'], [opt.name for opt in by_group['mailout']]
        )
        self.assertEqual(['page_size'], [opt.name for opt in by_group['nova']])
        self.assertIs(config.freshdesk_opts, by_group['freshdesk'])
        self.assertIs(config.mailout_opts, by_group['mailout'])
        self.assertIs(config.nova_opts, by_group['nova'])

    def test_opts_registered(self):
        """The options are registered on the global CONF at import"""
        self.assertIsNone(CONF.freshdesk.api_key)
        self.assertEqual(6000071619, CONF.freshdesk.email_config_id)
        self.assertEqual(6000208874, CONF.freshdesk.group_id)
        self.assertEqual('dhdnectar.freshdesk.com', CONF.freshdesk.domain)
        self.assertEqual(
            '~/.cache/os-mailout/freshdesk/', CONF.mailout.work_dir
        )
        self.assertEqual(-1, CONF.nova.page_size)

    def test_init_existing_file(self):
        pathname = os.path.join(self.tmpdir, 'nectar-osc.conf')
        with open(pathname, 'w') as f:
            f.write(
                '[freshdesk]\n'
                'api_key = sekrit\n'
                'domain = example.freshdesk.com\n'
                '[nova]\n'
                'page_size = 42\n'
            )
        out = self.capture_stdout()
        config.init(pathname)
        self.assertEqual('', out.getvalue())
        self.assertEqual('sekrit', CONF.freshdesk.api_key)
        self.assertEqual('example.freshdesk.com', CONF.freshdesk.domain)
        self.assertEqual(42, CONF.nova.page_size)
        # Unset options keep their defaults
        self.assertEqual(6000071619, CONF.freshdesk.email_config_id)

    def test_init_expands_user(self):
        """The config pathname is ~ expanded"""
        pathname = os.path.join(self.tmpdir, 'nectar-osc.conf')
        with open(pathname, 'w') as f:
            f.write('[nova]\npage_size = 7\n')
        with patch.dict(os.environ, {'HOME': self.tmpdir}):
            config.init('~/nectar-osc.conf')
        self.assertEqual(7, CONF.nova.page_size)

    def test_init_generates_missing_file(self):
        """A missing config file is generated from the registered opts"""
        pathname = os.path.join(self.tmpdir, 'nectar-osc.conf')
        self.assertFalse(os.path.exists(pathname))
        out = self.capture_stdout()
        config.init(pathname)
        self.assertIn(f'generating config file {pathname}', out.getvalue())
        self.assertTrue(os.path.exists(pathname))
        with open(pathname) as f:
            generated = f.read()
        self.assertIn('[DEFAULT]', generated)
        for group in ['freshdesk', 'mailout', 'nova']:
            self.assertIn(f'[{group}]', generated)
        for opt in ['api_key', 'email_config_id', 'group_id', 'domain']:
            self.assertIn(f'#{opt} = ', generated)
        self.assertIn('#work_dir = ~/.cache/os-mailout/freshdesk/', generated)
        self.assertIn('#page_size = -1', generated)

    def test_init_missing_directory(self):
        """If the config directory doesn't exist we bail out"""
        dirname = os.path.join(self.tmpdir, 'nowhere')
        pathname = os.path.join(dirname, 'nectar-osc.conf')
        out = self.capture_stdout()
        with self.assertRaises(SystemExit) as cm:
            config.init(pathname)
        self.assertEqual(1, cm.exception.code)
        self.assertIn(f'generating config file {pathname}', out.getvalue())
        self.assertIn(
            f"config directory {dirname} doesn't exist", out.getvalue()
        )
        self.assertFalse(os.path.exists(pathname))
