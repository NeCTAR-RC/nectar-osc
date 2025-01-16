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

from argparse import ArgumentError
from contextlib import contextmanager
import datetime
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import ANY
from unittest.mock import call
from unittest.mock import Mock
from unittest.mock import patch
import yaml

from keystoneclient.exceptions import NotFound
from nectarclient_lib.exceptions import BadRequest

from nectar_osc import mailout
from nectar_osc.tests.unit import fakes


INSTANCE_1 = {
    'addresses': ['192.168.76.119'],
    'email': 'fred.nurke@gmail.com',
    'flavor': '11111111-1111-1111-1111-111111111111',
    'fullname': 'Fred Nurke',
    'host': 'cn1.twilight.nectar.org.au',
    'id': '00000000-1111-1111-1111-111111111111',
    'image': '22222222-1111-1111-1111-111111111111',
    'name': 'one',
    'project': '44444444-1111-1111-1111-111111111111',
    'project_name': 'area54',
    'status': 'STOPPED',
    'user': '33333333-1111-1111-1111-111111111111',
    'zone': 'twilight',
}
INSTANCE_2 = {
    'addresses': ['192.168.76.112'],
    'email': 'fred.nurke@gmail.com',
    'flavor': '11111111-1111-1111-1111-111111111111',
    'fullname': 'Fred Nurke',
    'host': 'cn1.danger.nectar.org.au',
    'id': '00000000-1111-1111-1111-111111111112',
    'image': '22222222-1111-1111-1111-111111111112',
    'name': 'two',
    'project': '44444444-1111-1111-1111-111111111111',
    'project_name': 'area54',
    'status': 'ACTIVE',
    'user': '33333333-1111-1111-1111-111111111111',
    'zone': 'danger',
}


@contextmanager
def temp_template_file(text):
    (fd, pathname) = tempfile.mkstemp(
        dir='/tmp', suffix='.tmpl', prefix='mailout', text=True
    )
    with os.fdopen(fd, 'w') as f:
        f.write(text)
    try:
        yield pathname
    finally:
        os.remove(pathname)


@contextmanager
def temp_workdir(delete_on_completion=True):
    pathname = tempfile.mkdtemp()
    try:
        yield pathname
    finally:
        if delete_on_completion and os.path.exists(pathname):
            shutil.rmtree(pathname)


TEST_TEMPLATE = """
days: {{ days }}
hours: {{ hours }}
start_ts: {{ start_ts }}
end_ts: {{ end_ts }}
tz: {{ tz }}
instances: {{ instances }}
"""


class TestMailout(unittest.TestCase):
    def test_get_parser(self):
        mock_app = Mock()
        mock_app_args = Mock()
        command = mailout.Instances(mock_app, mock_app_args)
        self.assertIsNotNone(command)
        parser = command.get_parser("instances")
        self.assertIsNotNone(parser)

    def test_check_args(self):
        mock_app = Mock()
        mock_app_args = Mock()
        FAILURE_TESTS = [
            ([], Exception, 'No --start-time'),
            (['--start-time'], ArgumentError, 'expected one argument'),
            (['--start-time', 'foo'], Exception, 'expected date-time format'),
            (['--start-time', '09:00 25-06-2015'], Exception, 'No --duration'),
            (
                ['--start-time', '09:00 25-06-2015', '--duration'],
                ArgumentError,
                'expected one argument',
            ),
            (
                ['--start-time', '09:00 25-06-2015', '--duration', 'fubar'],
                Exception,
                'integer is required',
            ),
            (
                ['--start-time', '09:00 25-06-2015', '--duration=-1'],
                Exception,
                'cannot be negative',
            ),
            (
                ['--start-time', '09:00 25-06-2015', '--duration', '0'],
                Exception,
                'No template',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                ],
                ArgumentError,
                'expected one argument',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/foo/bar',
                ],
                Exception,
                'could not be found',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/foo/bar',
                ],
                Exception,
                'could not be found',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--limit',
                ],
                ArgumentError,
                'expected one argument',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--limit',
                    'fubar',
                ],
                Exception,
                'integer is required',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--instances-file',
                ],
                ArgumentError,
                'expected one argument',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--instances-file',
                    '/foo/bar',
                ],
                Exception,
                'could not be found',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--user',
                    'jim.spriggs@gmail.com',
                ],
                NotFound,
                '404',
            ),
            (
                [
                    '--start-time',
                    '09:00 25-06-2015',
                    '--duration',
                    '0',
                    '--template',
                    '/etc/passwd',
                    '--project',
                    'route66',
                ],
                NotFound,
                '404',
            ),
        ]
        for args, exc, regex in FAILURE_TESTS:
            command = mailout.Instances(mock_app, mock_app_args)
            parser = command.get_parser("instances")
            command.clients = fakes.make_fake_clients()

            if sys.version[0] == 3 and sys.version[1] >= 9:
                parser.exit_on_error = False
                with self.assertRaisesRegex(exc, regex):
                    command.check_args(parser.parse_args(args))
            elif exc != ArgumentError:
                with self.assertRaisesRegex(exc, regex):
                    command.check_args(parser.parse_args(args))
            else:
                # prior to Python 3.9, we can't stop argparse
                # from exiting when it detects a syntax error
                with self.assertRaises(SystemExit):
                    command.check_args(parser.parse_args(args))

    def test_check_args2(self):
        mock_app = Mock()
        mock_app_args = Mock()
        command = mailout.Instances(mock_app, mock_app_args)
        parser = command.get_parser("instances")
        command.clients = fakes.make_fake_clients()
        args = [
            '--start-time=09:00 25-06-2015',
            '--duration=1',
            '--limit=1',
            '--template=/etc/passwd',
            '--instances-file=/etc/passwd',
            '--work-dir=/tmp',
            '--zone=here',
            '--zone=there',
            '--ip=127.0.0.1',
            '--ip=1.2.3.4',
            '--node=a.b.nectar.org.au',
            '--node=c.d.nectar.org.au',
            '--image=xxxx',
            '--status=STOPPED',
            '--subject=To change',
            '--record-metadata',
            '--metadata-field=ticket-id',
            '--user=fred.nurke@gmail.com',
            '--project=area54',
        ]
        command.check_args(parser.parse_args(args))
        self.assertEqual(1, command.limit)
        self.assertEqual('/etc/passwd', command.template)
        self.assertEqual('/etc/passwd', command.instances_file)
        self.assertEqual('/tmp', command.work_dir)
        self.assertEqual('STOPPED', command.status)
        self.assertEqual(['here', 'there'], command.zones)
        self.assertEqual(['127.0.0.1', '1.2.3.4'], command.ips)
        self.assertEqual(
            ['a.b.nectar.org.au', 'c.d.nectar.org.au'], command.nodes
        )
        self.assertEqual('xxxx', command.image)
        self.assertEqual('To change', command.subject)
        self.assertEqual('AEDT', command.timezone)
        self.assertTrue(command.record_metadata)
        self.assertEqual('ticket-id', command.metadata_field)
        self.assertEqual(
            datetime.datetime(2015, 6, 25, 9, 0), command.start_ts
        )
        self.assertEqual(datetime.datetime(2015, 6, 25, 10, 0), command.end_ts)
        self.assertIsNotNone(command.user_id)
        self.assertIsNotNone(command.project_id)

    def _load(self, path):
        with open(path) as file:
            return yaml.load(file, Loader=yaml.FullLoader)

    def _prep(self, test_workdir):
        "Prepare a workdir for send and clean tests"

        mock_app = Mock()
        mock_app_args = Mock()
        mock_app.client_manager = fakes.make_fake_clients()
        with temp_template_file(TEST_TEMPLATE) as test_template_path:
            command = mailout.Instances(mock_app, mock_app_args)
            parser = command.get_parser("instances")
            command.clients = fakes.make_fake_clients()
            args = [
                '--start-time=09:00 25-06-2015',
                '--duration=1',
                '--work-dir',
                test_workdir,
                '--template',
                test_template_path,
                '--subject=To change',
            ]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)

            self.assertTrue(command.mailout_dir)
            notifications = [f for f in os.listdir(command.mailout_dir)]
            self.assertEqual(2, len(notifications))

        return command.mailout_dir

    def test_instances(self):
        mock_app = Mock()
        mock_app_args = Mock()
        mock_app.client_manager = fakes.make_fake_clients()
        with temp_workdir() as test_workdir:
            with temp_template_file(TEST_TEMPLATE) as test_template_path:
                command = mailout.Instances(mock_app, mock_app_args)
                parser = command.get_parser("instances")
                command.clients = fakes.make_fake_clients()
                args = [
                    '--start-time=09:00 25-06-2015',
                    '--duration=1',
                    '--work-dir',
                    test_workdir,
                    '--template',
                    test_template_path,
                    '--subject=To change',
                ]
                parsed_args = parser.parse_args(args)
                command.take_action(parsed_args)

                self.assertTrue(command.mailout_dir)
                notifications = [f for f in os.listdir(command.mailout_dir)]
                self.assertEqual(2, len(notifications))
                self.assertIn('notification@area54', notifications)
                self.assertIn('notification@sanandreas', notifications)
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                self.assertEqual(0, loaded['SeqNo'])
                self.assertTrue(loaded['Body'])
                self.assertEqual('area54', loaded['Key'])
                self.assertEqual('To change', loaded['Subject'])
                self.assertEqual(
                    ['fred.nurke@gmail.com', 'terry.towling@gmail.com'],
                    loaded['SendTo'],
                )
                self.assertEqual(
                    {
                        'days': 0,
                        'hours': 1,
                        'start_ts': datetime.datetime(2015, 6, 25, 9, 0),
                        'end_ts': datetime.datetime(2015, 6, 25, 10, 0),
                        'instances': [INSTANCE_1, INSTANCE_2],
                        'project_name': 'area54',
                        'recipients': [
                            'fred.nurke@gmail.com',
                            'terry.towling@gmail.com',
                        ],
                    },
                    loaded['Context'],
                )

    def test_cleanup(self):
        mock_app = Mock()
        mock_app_args = Mock()
        with temp_workdir() as test_workdir:
            self._prep(test_workdir)
            self.assertTrue(os.path.exists(test_workdir))

            command = mailout.Cleanup(mock_app, mock_app_args)
            parser = command.get_parser("clean")
            args = [
                '--work-dir',
                test_workdir,
                '--all',
            ]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)

            self.assertFalse(os.path.exists(test_workdir))

        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self.assertTrue(os.path.exists(mailout_dir))

            command = mailout.Cleanup(mock_app, mock_app_args)
            parser = command.get_parser("clean")
            args = ['--work-dir', test_workdir, '--mailout-dir', mailout_dir]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)

            self.assertTrue(os.path.exists(test_workdir))
            self.assertFalse(os.path.exists(mailout_dir))

    def test_send(self):
        mock_app = Mock()
        mock_app_args = Mock()
        mock_taynac = Mock()
        mock_app.client_manager = fakes.make_fake_clients(taynac=mock_taynac)
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self.assertTrue(os.path.exists(test_workdir))

            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("send")
            args = ['--mailout-dir', mailout_dir, "--confirm"]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)
            mock_taynac.messages.send.assert_has_calls(
                [
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='fred.nurke@gmail.com',
                        cc=['terry.towling@gmail.com'],
                    ),
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='randy.katz@gmail.com',
                        cc=[],
                    ),
                ],
                any_order=True,
            )
            last_path = os.path.join(mailout_dir, 'LAST_SENT')
            self.assertTrue(os.path.exists(last_path))
            with open(last_path) as last_file:
                self.assertEqual('1', last_file.readline())

    def test_send_to(self):
        mock_app = Mock()
        mock_app_args = Mock()
        mock_taynac = Mock()
        mock_app.client_manager = fakes.make_fake_clients(taynac=mock_taynac)
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self.assertTrue(os.path.exists(test_workdir))

            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("send")
            args = [
                '--mailout-dir',
                mailout_dir,
                "--confirm",
                '--send-to',
                'operator.bob@ardc.edu.au',
            ]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)
            mock_taynac.messages.send.assert_has_calls(
                [
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='operator.bob@ardc.edu.au',
                        cc=[],
                    ),
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='operator.bob@ardc.edu.au',
                        cc=[],
                    ),
                ],
                any_order=True,
            )
            # In '--send-to' mode, LAST_SENT is not updated
            last_path = os.path.join(mailout_dir, 'LAST_SENT')
            self.assertFalse(os.path.exists(last_path))

    def test_send_fail_and_resume(self):
        mock_app = Mock()
        mock_app_args = Mock()
        mock_taynac = Mock()
        mock_app.client_manager = fakes.make_fake_clients(taynac=mock_taynac)
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self.assertTrue(os.path.exists(test_workdir))

            # Simulate send failure
            mock_taynac.messages.send.side_effect = [
                {'backend_id', '1234'},
                BadRequest,
            ]
            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("send")
            args = ['--mailout-dir', mailout_dir, "--confirm"]
            parsed_args = parser.parse_args(args)
            with self.assertRaises(BadRequest):
                command.take_action(parsed_args)
            mock_taynac.messages.send.assert_has_calls(
                [
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='fred.nurke@gmail.com',
                        cc=['terry.towling@gmail.com'],
                    ),
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='randy.katz@gmail.com',
                        cc=[],
                    ),
                ],
                any_order=True,
            )

            last_path = os.path.join(mailout_dir, 'LAST_SENT')
            self.assertTrue(os.path.exists(last_path))
            with open(last_path) as last_file:
                self.assertEqual('0', last_file.readline())

            # Check the 'already sent' logic
            mock_taynac.messages.send.reset_mock()
            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("send")
            args = ['--mailout-dir', mailout_dir, "--confirm"]
            parsed_args = parser.parse_args(args)
            with self.assertRaisesRegex(Exception, 'been sent already'):
                command.take_action(parsed_args)
            mock_taynac.messages.send.assert_not_called()

            # Check resumption
            mock_taynac.messages.send.side_effect = [
                {'backend_id', '1235'},
            ]
            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("clean")
            args = ['--mailout-dir', mailout_dir, "--confirm", "--resume"]
            parsed_args = parser.parse_args(args)
            command.take_action(parsed_args)
            mock_taynac.messages.send.assert_has_calls(
                [
                    call(
                        subject='To change',
                        body=ANY,
                        recipient='randy.katz@gmail.com',
                        cc=[],
                    ),
                ],
            )

            with open(last_path) as last_file:
                self.assertEqual('1', last_file.readline())

    @patch('nectar_osc.mailout.query_yes_no')
    def test_send_confirm(self, mock_query_yes_no):
        mock_app = Mock()
        mock_app_args = Mock()
        mock_app.client_manager = fakes.make_fake_clients()
        mock_query_yes_no.return_value = False
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self.assertTrue(os.path.exists(test_workdir))

            command = mailout.Send(mock_app, mock_app_args)
            parser = command.get_parser("send")
            args = ['--mailout-dir', mailout_dir]
            parsed_args = parser.parse_args(args)
            with self.assertRaises(SystemExit):
                command.take_action(parsed_args)
