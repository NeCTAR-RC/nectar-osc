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
from unittest.mock import ANY
from unittest.mock import call
from unittest.mock import Mock
from unittest.mock import patch
import yaml

from jinja2.exceptions import TemplateNotFound
from jinja2.exceptions import UndefinedError
from keystoneclient.exceptions import NotFound
from nectarclient_lib.exceptions import BadRequest

from nectar_osc import identity
from nectar_osc import mailout
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


INSTANCE_1 = {
    'addresses': ['192.168.76.119'],
    'email': 'fred.nurke@gmail.com',
    'flavor': '11111111-1111-1111-1111-111111111111',
    'fullname': 'Fred Nurke',
    'host': 'cn1',
    'full_host': 'cn1.twilight.nectar.org.au',
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
    'host': 'cn1',
    'full_host': 'cn1.danger.nectar.org.au',
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

# A template that only uses the context that is always provided
SIMPLE_TEMPLATE = """
project: {{ project_name }}
affected: {{ affected }}
instances: {{ instances }}
"""


class TestMailout(test.TestCase):
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
            (['--timezone'], ArgumentError, 'expected one argument'),
            (
                ['--timezone', 'blort'],
                Exception,
                "Unrecognized timezone 'blort'",
            ),
            (['--start-time'], ArgumentError, 'expected one argument'),
            (['--start-time', 'foo'], Exception, 'expected date-time format'),
            (
                ['--duration', '42'],
                Exception,
                '--duration can only be used with --start-time',
            ),
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
                    '--node',
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
            '--template=/etc/passwd',
            '--instances-file=/etc/passwd',
            '--work-dir=/tmp',
            '--zone=here',
            '--zone=there',
            '--ip=127.0.0.1',
            '--ip=1.2.3.4',
            '--node=host1',
            '--node=host2',
            '--image=xxxx',
            '--status=STOPPED',
            '--subject=To change',
            '--record-metadata',
            '--metadata-field=ticket-id',
            '--user=fred.nurke@gmail.com',
            '--project=area54',
        ]
        command.check_args(parser.parse_args(args))
        self.assertIsNone(command.limit)
        self.assertEqual('/etc/passwd', command.template)
        self.assertEqual('/etc/passwd', command.instances_file)
        self.assertEqual('/tmp', command.work_dir)
        self.assertEqual('STOPPED', command.status)
        self.assertEqual(['here', 'there'], command.zones)
        self.assertEqual(['127.0.0.1', '1.2.3.4'], command.ips)
        self.assertEqual(['host1', 'host2'], command.nodes)
        self.assertEqual('xxxx', command.image)
        self.assertEqual('To change', command.subject)
        self.assertIsNone(command.timezone)
        self.assertTrue(command.record_metadata)
        self.assertEqual('ticket-id', command.metadata_field)
        self.assertEqual(
            datetime.datetime(2015, 6, 25, 9, 0).astimezone(),
            command.start_ts,
        )
        self.assertEqual(
            datetime.datetime(2015, 6, 25, 10, 0).astimezone(),
            command.end_ts,
        )
        self.assertIsNotNone(command.user_id)
        self.assertIsNotNone(command.project_id)

    def test_check_args3(self):
        mock_app = Mock()
        mock_app_args = Mock()
        command = mailout.Instances(mock_app, mock_app_args)
        parser = command.get_parser("instances")
        command.clients = fakes.make_fake_clients()
        args = [
            '--start-time=09:00 25-06-2015',
            '--duration=1',
            '--timezone=Australia/Perth',
            '--template=/etc/passwd',
        ]
        command.check_args(parser.parse_args(args))
        self.assertIsNone(command.limit)
        self.assertEqual('/etc/passwd', command.template)
        self.assertIsNone(command.instances_file)
        self.assertIsNotNone(command.work_dir)
        self.assertEqual('ALL', command.status)
        self.assertIsNone(command.zones)
        self.assertIsNone(command.ips)
        self.assertIsNone(command.nodes)
        self.assertIsNone(command.image)
        self.assertEqual(
            (
                'Important announcement about project {{ project_name }} instances'
            ),
            command.subject,
        )
        self.assertEqual('Australia/Perth', command.timezone.key)
        self.assertFalse(command.record_metadata)
        self.assertIsNone(command.metadata_field)
        self.assertEqual(
            datetime.datetime(2015, 6, 25, 9, 0, tzinfo=command.timezone),
            command.start_ts,
        )
        self.assertEqual(command.timezone, command.start_ts.tzinfo)
        self.assertEqual(
            datetime.datetime(2015, 6, 25, 10, 0, tzinfo=command.timezone),
            command.end_ts,
        )
        self.assertEqual(command.timezone, command.end_ts.tzinfo)
        self.assertIsNone(command.user_id)
        self.assertIsNone(command.project_id)

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
            notifications = [
                f
                for f in os.listdir(command.mailout_dir)
                if f.startswith('notification@')
            ]
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
                    '--subject=To change in {{ project_name }}',
                ]
                parsed_args = parser.parse_args(args)
                command.take_action(parsed_args)

                self.assertTrue(command.mailout_dir)
                notifications = [
                    f
                    for f in os.listdir(command.mailout_dir)
                    if f.startswith('notification@')
                ]
                self.assertEqual(2, len(notifications))
                self.assertIn('notification@area54', notifications)
                self.assertIn('notification@sanandreas', notifications)
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                self.assertEqual(0, loaded['SeqNo'])
                self.assertTrue(loaded['Body'])
                self.assertEqual('area54', loaded['Key'])
                self.assertEqual('To change in area54', loaded['Subject'])
                self.assertEqual(
                    ['fred.nurke@gmail.com', 'terry.towling@gmail.com'],
                    loaded['SendTo'],
                )
                self.assertEqual(
                    {
                        'affected': 2,
                        'days': 0,
                        'hours': 1,
                        'start_ts': datetime.datetime(
                            2015, 6, 25, 9, 0
                        ).astimezone(),
                        'end_ts': datetime.datetime(
                            2015, 6, 25, 10, 0
                        ).astimezone(),
                        'tz': 'AEST',
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

    def _make_recipients_command(
        self, project_id, n_managers, n_members, disabled_emails=()
    ):
        """Build an Instances command whose fake identity has a project
        with the given numbers of TenantManagers and Members.  Manager
        emails are 'managerN@example.com', member emails are
        'memberN@example.com'.
        """
        member_role_id = fakes.ROLES[0].id
        manager_role_id = fakes.ROLES[1].id
        users = []
        assignments = []
        specs = [
            ('manager', manager_role_id, n_managers),
            ('member', member_role_id, n_members),
        ]
        for prefix, role_id, count in specs:
            for i in range(count):
                email = f'{prefix}{i}@example.com'
                user_id = f'{prefix}-{i}'
                users.append(
                    fakes.FakeUser(
                        id=user_id,
                        name=email,
                        email=email,
                        full_name=f'{prefix} {i}',
                        enabled=email not in disabled_emails,
                    )
                )
                assignments.append(
                    fakes.FakeRoleAssignment(
                        user_id=user_id,
                        project_id=project_id,
                        role_id=role_id,
                    )
                )
        command = mailout.Instances(Mock(), Mock())
        command.clients = fakes.make_fake_clients(
            users=users, assignments=assignments
        )
        return command

    def _select_recipients(
        self, n_managers, n_members, disabled_emails=(), prefetch=False
    ):
        project_id = '44444444-2222-2222-2222-222222222222'
        command = self._make_recipients_command(
            project_id, n_managers, n_members, disabled_emails
        )
        if prefetch:
            command.assignments = identity.get_role_assignments_by_project(
                command.clients.identity, mailout.RECIPIENT_ROLES
            )
        return command.select_recipients(
            command.clients.identity, project_id, 'testproject'
        )

    def test_select_recipients_small_project(self):
        recipients = self._select_recipients(n_managers=2, n_members=3)
        self.assertEqual(
            [
                'manager0@example.com',
                'manager1@example.com',
                'member0@example.com',
                'member1@example.com',
                'member2@example.com',
            ],
            recipients,
        )

    def test_select_recipients_many_managers(self):
        recipients = self._select_recipients(n_managers=6, n_members=3)
        self.assertEqual(
            [f'manager{i}@example.com' for i in range(6)], recipients
        )

    def test_select_recipients_large_project(self):
        recipients = self._select_recipients(n_managers=2, n_members=30)
        self.assertEqual(
            ['manager0@example.com', 'manager1@example.com'], recipients
        )

    def test_select_recipients_manager_cap(self):
        recipients = self._select_recipients(n_managers=25, n_members=0)
        self.assertEqual(
            [f'manager{i}@example.com' for i in range(20)], recipients
        )

    def test_select_recipients_excludes_disabled(self):
        recipients = self._select_recipients(
            n_managers=1,
            n_members=2,
            disabled_emails=('member0@example.com',),
        )
        self.assertEqual(
            ['manager0@example.com', 'member1@example.com'], recipients
        )

    def test_select_recipients_prefetched(self):
        """The prefetched (bulk role-assignment) path must select the
        same recipients as the per-project query path.
        """
        for kwargs in [
            dict(n_managers=2, n_members=3),
            dict(n_managers=6, n_members=3),
            dict(n_managers=2, n_members=30),
            dict(n_managers=25, n_members=0),
            dict(
                n_managers=1,
                n_members=2,
                disabled_emails=('member0@example.com',),
            ),
        ]:
            identity.clear_caches()
            expected = self._select_recipients(**kwargs)
            identity.clear_caches()
            self.assertEqual(
                expected,
                self._select_recipients(prefetch=True, **kwargs),
                f"prefetched path differs for {kwargs}",
            )

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

    @patch('nectar_osc.mailout.query_yes_no')
    def test_send_confirmed(self, mock_query_yes_no):
        mock_taynac = Mock()
        mock_app = Mock()
        mock_app.client_manager = fakes.make_fake_clients(taynac=mock_taynac)
        mock_query_yes_no.return_value = True
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            command = mailout.Send(mock_app, Mock())
            parser = command.get_parser("send")
            out = self.capture_stdout()
            command.take_action(
                parser.parse_args(['--mailout-dir', mailout_dir])
            )
            mock_query_yes_no.assert_called_once_with(
                "Do you want to send them now?", default='no'
            )
            self.assertIn(
                'CAUTION: this will send 2 notifications', out.getvalue()
            )
            self.assertEqual(2, mock_taynac.messages.send.call_count)

    # -- Instances: argument handling --

    def test_get_parser_defaults(self):
        command = mailout.Instances(Mock(), Mock())
        args = command.get_parser("instances").parse_args([])
        self.assertIsNone(args.template)
        self.assertEqual(
            os.path.expanduser('~/.cache/os-mailout/freshdesk/'),
            args.work_dir,
        )
        self.assertEqual('ALL', args.status)
        self.assertFalse(args.record_metadata)
        for name in [
            'zone',
            'ip',
            'node',
            'image',
            'user',
            'project',
            'subject',
            'start_time',
            'duration',
            'timezone',
            'instances_file',
            'metadata_field',
            'limit',
        ]:
            self.assertIsNone(getattr(args, name), name)

    def _check_args(self, args):
        command = mailout.Instances(Mock(), Mock())
        parser = command.get_parser("instances")
        command.clients = fakes.make_fake_clients()
        command.check_args(parser.parse_args(args))
        return command

    def test_check_args_start_time_only(self):
        command = self._check_args(
            ['--start-time=09:00 25-06-2015', '--template=/etc/passwd']
        )
        start_ts = datetime.datetime(2015, 6, 25, 9, 0).astimezone()
        self.assertEqual(start_ts, command.start_ts)
        self.assertIsNone(command.end_ts)
        self.assertIsNone(command.timezone)
        # Without --timezone, the local timezone name is used
        self.assertEqual(start_ts.tzinfo.tzname(start_ts), command.tzname)

    def test_check_args_no_times(self):
        command = self._check_args(['--template=/etc/passwd'])
        self.assertIsNone(command.start_ts)
        self.assertIsNone(command.end_ts)
        self.assertIsNone(command.timezone)
        self.assertIsNone(command.tzname)

    def test_check_args_timezone_only(self):
        command = self._check_args(
            ['--timezone=Australia/Perth', '--template=/etc/passwd']
        )
        self.assertIsNone(command.start_ts)
        self.assertEqual('Australia/Perth', command.timezone.key)
        self.assertEqual('Australia/Perth', command.tzname)

    def test_check_args_limit(self):
        command = self._check_args(['--limit=3', '--template=/etc/passwd'])
        self.assertEqual(3, command.limit)
        for limit in ['0', '-5']:
            with self.assertRaisesRegex(Exception, 'must be >= 1'):
                self._check_args(
                    [f'--limit={limit}', '--template=/etc/passwd']
                )
        with self.assertRaisesRegex(
            Exception, '--limit cannot be used with --instances-file'
        ):
            self._check_args(
                [
                    '--limit=3',
                    '--instances-file=/etc/passwd',
                    '--template=/etc/passwd',
                ]
            )

    def test_check_args_user_and_project_by_id(self):
        command = self._check_args(
            [
                '--template=/etc/passwd',
                '--user=33333333-1111-1111-1111-111111111113',
                '--project=44444444-1111-1111-1111-111111111112',
            ]
        )
        self.assertEqual(
            '33333333-1111-1111-1111-111111111113', command.user_id
        )
        self.assertEqual(
            '44444444-1111-1111-1111-111111111112', command.project_id
        )

    # -- MailoutPrepCommand helpers --

    def test_setup(self):
        mock_app = Mock()
        mock_app.client_manager = fakes.make_fake_clients()
        with temp_workdir() as test_workdir:
            with temp_template_file(TEST_TEMPLATE) as test_template_path:
                # The work dir is created if needed
                work_dir = os.path.join(test_workdir, 'work', 'dir')
                self.assertFalse(os.path.exists(work_dir))
                command = mailout.Instances(mock_app, Mock())
                parser = command.get_parser("instances")
                parsed_args = parser.parse_args(
                    ['--work-dir', work_dir, '--template', test_template_path]
                )
                out = self.capture_stdout()
                command.setup(parsed_args)
                self.assertTrue(os.path.isdir(work_dir))
                self.assertIs(mock_app.client_manager, command.clients)
                self.assertIsInstance(command.generator, mailout.Generator)
                self.assertEqual(0, command.count)
                self.assertTrue(os.path.isdir(command.mailout_dir))
                self.assertEqual(
                    work_dir, os.path.dirname(command.mailout_dir)
                )
                self.assertEqual(
                    f"Mailout will be prepared in directory "
                    f"{command.mailout_dir}\n",
                    out.getvalue(),
                )

    def test_read_ids(self):
        with temp_template_file('id-1\nid-2\n\nid-3\n') as ids_file:
            command = mailout.Instances(Mock(), Mock())
            self.assertEqual(
                ['id-1', 'id-2', '', 'id-3'], list(command.read_ids(ids_file))
            )

    def test_generate_notification(self):
        with temp_workdir() as mailout_dir:
            with temp_template_file(
                'Hello {{ project_name }}: {{ affected }} affected'
            ) as template:
                command = mailout.Instances(Mock(), Mock())
                command.generator = mailout.Generator(
                    template, 'About {{ project_name }}'
                )
                command.mailout_dir = mailout_dir
                command.count = 0
                context = {'project_name': 'Group/Team', 'affected': 3}
                command.generate_notification(
                    'Group/Team', ['a@example.com', 'b@example.com'], context
                )
                self.assertEqual(1, command.count)
                # The filename is normalized, the key is not
                self.assertEqual(
                    ['notification@Group_Team'], os.listdir(mailout_dir)
                )
                self.assertEqual(
                    {
                        'SeqNo': 0,
                        'Key': 'Group/Team',
                        'Subject': 'About Group/Team',
                        'Body': 'Hello Group/Team: 3 affected',
                        'SendTo': ['a@example.com', 'b@example.com'],
                        'Context': context,
                    },
                    self._load(
                        os.path.join(mailout_dir, 'notification@Group_Team')
                    ),
                )
                # Never overwrite a notification
                with self.assertRaisesRegex(
                    Exception,
                    'Notification file notification@Group_Team '
                    'already exists!',
                ):
                    command.generate_notification(
                        'Group/Team', ['a@example.com'], context
                    )
                self.assertEqual(1, command.count)

    # -- Instances: take_action variants --

    def _run_instances(
        self, test_workdir, template_path, extra_args, clients=None
    ):
        mock_app = Mock()
        mock_app.client_manager = clients or fakes.make_fake_clients()
        command = mailout.Instances(mock_app, Mock())
        parser = command.get_parser("instances")
        args = [
            '--work-dir',
            test_workdir,
            '--template',
            template_path,
        ] + extra_args
        out = self.capture_stdout()
        command.take_action(parser.parse_args(args))
        return command, out.getvalue()

    def _notifications(self, mailout_dir):
        return sorted(
            f for f in os.listdir(mailout_dir) if f.startswith('notification@')
        )

    def _instances_list(self, mailout_dir):
        with open(os.path.join(mailout_dir, 'instances.list')) as f:
            return sorted(line.strip() for line in f if line.strip())

    def test_instances_prefetch(self):
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                command, output = self._run_instances(
                    test_workdir, test_template_path, []
                )
                self.assertIn(
                    'Prefetching users, projects and roles...', output
                )
                self.assertIn(
                    'Prefetched 4 users, 3 projects and the role '
                    'assignments of 2 projects',
                    output,
                )
                self.assertIn('Collected 4 instances', output)
                self.assertIn('Selected recipients for 2 projects', output)
                self.assertIn('Will generate 2 notifications', output)
                self.assertIn(
                    f'Generated 2 notifications into {command.mailout_dir}',
                    output,
                )
                self.assertEqual(
                    set(command.assignments),
                    {
                        '44444444-1111-1111-1111-111111111111',
                        '44444444-1111-1111-1111-111111111112',
                    },
                )
                # Every instance (even those with no recipients) is
                # listed in the instances file
                self.assertEqual(
                    sorted(s.id for s in fakes.SERVERS),
                    self._instances_list(command.mailout_dir),
                )
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                # No times were given
                for key in ['start_ts', 'end_ts', 'tz', 'days', 'hours']:
                    self.assertNotIn(key, loaded['Context'])
                self.assertEqual(
                    'Important announcement about project area54 instances',
                    loaded['Subject'],
                )

    def test_instances_from_file(self):
        ids = [
            '00000000-1111-1111-1111-111111111111',
            '00000000-1111-1111-1111-111111111112',
            '00000000-1111-1111-1111-111111111112',  # duplicate
            '00000000-9999-9999-9999-999999999999',  # unknown
        ]
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                with temp_template_file('\n'.join(ids) + '\n') as ids_file:
                    command, output = self._run_instances(
                        test_workdir,
                        test_template_path,
                        ['--instances-file', ids_file],
                    )
                self.assertIn(
                    "Instance '00000000-9999-9999-9999-999999999999' "
                    "not found: skipping it.",
                    output,
                )
                self.assertIn('Collected 2 instances', output)
                self.assertEqual(
                    ids[:2], self._instances_list(command.mailout_dir)
                )
                self.assertEqual(
                    ['notification@area54'],
                    self._notifications(command.mailout_dir),
                )
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                self.assertEqual(2, loaded['Context']['affected'])
                self.assertEqual(
                    ids[:2],
                    sorted(i['id'] for i in loaded['Context']['instances']),
                )

    def test_instances_zones(self):
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                command, output = self._run_instances(
                    test_workdir,
                    test_template_path,
                    ['--zone', 'danger', '--timezone', 'Australia/Perth'],
                )
                self.assertIn('Collected 3 instances', output)
                self.assertEqual(
                    ['notification@area54', 'notification@sanandreas'],
                    self._notifications(command.mailout_dir),
                )
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                self.assertEqual(['danger'], loaded['Context']['zones'])
                self.assertEqual('Australia/Perth', loaded['Context']['tz'])
                self.assertEqual(1, loaded['Context']['affected'])
                self.assertEqual([INSTANCE_2], loaded['Context']['instances'])
                loaded = self._load(
                    os.path.join(
                        command.mailout_dir, 'notification@sanandreas'
                    )
                )
                self.assertEqual(2, loaded['Context']['affected'])
                self.assertEqual(['randy.katz@gmail.com'], loaded['SendTo'])

    def test_instances_project(self):
        """A single project mailout skips the bulk prefetch"""
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                command, output = self._run_instances(
                    test_workdir, test_template_path, ['--project', 'area54']
                )
                self.assertNotIn('Prefetching', output)
                self.assertEqual({}, command.assignments)
                self.assertIn('Collected 2 instances', output)
                self.assertEqual(
                    ['notification@area54'],
                    self._notifications(command.mailout_dir),
                )
                loaded = self._load(
                    os.path.join(command.mailout_dir, 'notification@area54')
                )
                self.assertEqual(
                    ['fred.nurke@gmail.com', 'terry.towling@gmail.com'],
                    loaded['SendTo'],
                )

    def test_instances_user(self):
        """A single user mailout skips the bulk prefetch and picks up
        the user's tier 2 (trove) instances.
        """
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                command, output = self._run_instances(
                    test_workdir,
                    test_template_path,
                    ['--user', 'randy.katz@gmail.com'],
                )
                self.assertNotIn('Prefetching', output)
                self.assertIn('Collected 2 instances', output)
                self.assertEqual(
                    ['notification@sanandreas'],
                    self._notifications(command.mailout_dir),
                )
                self.assertEqual(
                    [
                        '00000000-1111-1111-1111-111111111113',
                        '00000000-1111-1111-1111-111111111114',
                    ],
                    self._instances_list(command.mailout_dir),
                )

    def test_instances_limit(self):
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                command, output = self._run_instances(
                    test_workdir, test_template_path, ['--limit', '1']
                )
                self.assertIn('Collected 1 instances', output)
                self.assertEqual(
                    ['00000000-1111-1111-1111-111111111111'],
                    self._instances_list(command.mailout_dir),
                )

    def test_instances_no_recipients(self):
        """Projects without any (enabled) users to notify are skipped,
        but their instances are still recorded in the instances file.
        """
        with temp_workdir() as test_workdir:
            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                # Nobody holds any roles at all ...
                command, output = self._run_instances(
                    test_workdir,
                    test_template_path,
                    [],
                    clients=fakes.make_fake_clients(assignments=[]),
                )
                self.assertIn('Collected 4 instances', output)
                self.assertIn('Selected recipients for 0 projects', output)
                self.assertIn('Will generate 0 notifications', output)
                self.assertEqual([], self._notifications(command.mailout_dir))
                self.assertEqual(
                    sorted(s.id for s in fakes.SERVERS),
                    self._instances_list(command.mailout_dir),
                )

            with temp_template_file(SIMPLE_TEMPLATE) as test_template_path:
                # ... or every role holder is disabled
                identity.clear_caches()
                users = [
                    fakes.FakeUser(
                        id=u.id,
                        name=u.name,
                        email=u.email,
                        full_name=u.full_name,
                        enabled=False,
                    )
                    for u in fakes.USERS
                ]
                command, output = self._run_instances(
                    test_workdir,
                    test_template_path,
                    ['--project', 'area54'],
                    clients=fakes.make_fake_clients(users=users),
                )
                self.assertIn('Collected 2 instances', output)
                self.assertIn('Will generate 0 notifications', output)
                self.assertEqual([], self._notifications(command.mailout_dir))

    # -- Cleanup --

    def test_cleanup_check_args(self):
        with temp_workdir() as test_workdir:
            for args, regex in [
                ([], 'Require one'),
                (['--all', '--mailout-dir', test_workdir], 'Require one'),
                (
                    ['--mailout-dir', '/no/such/dir'],
                    "'/no/such/dir' not found",
                ),
            ]:
                command = mailout.Cleanup(Mock(), Mock())
                parser = command.get_parser("cleanup")
                with self.assertRaisesRegex(Exception, regex):
                    command.take_action(parser.parse_args(args))
            # Nothing was removed
            self.assertTrue(os.path.exists(test_workdir))

    # -- Send --

    def test_send_check_args(self):
        with temp_workdir() as test_workdir:
            for args, regex in [
                ([], '--mailout-dir <directory> option is required'),
                (
                    ['--mailout-dir', '/no/such/dir'],
                    "'/no/such/dir' not found",
                ),
                (
                    ['--mailout-dir', test_workdir, '--limit', 'fubar'],
                    'integer is required',
                ),
                (
                    ['--mailout-dir', test_workdir, '--limit', '-1'],
                    'must be >= 1',
                ),
            ]:
                command = mailout.Send(Mock(), Mock())
                parser = command.get_parser("send")
                with self.assertRaisesRegex(Exception, regex):
                    command.check_args(parser.parse_args(args))

            command = mailout.Send(Mock(), Mock())
            parser = command.get_parser("send")
            command.check_args(
                parser.parse_args(['--mailout-dir', test_workdir])
            )
            self.assertEqual(test_workdir, command.mailout_dir)
            self.assertIsNone(command.limit)
            self.assertFalse(command.resume)
            self.assertFalse(command.confirm)
            self.assertIsNone(command.send_to)

            command.check_args(
                parser.parse_args(
                    [
                        '--mailout-dir',
                        test_workdir,
                        '--limit',
                        '5',
                        '--resume',
                        '--confirm',
                        '--send-to',
                        'bob@example.com',
                    ]
                )
            )
            self.assertEqual(5, command.limit)
            self.assertTrue(command.resume)
            self.assertTrue(command.confirm)
            self.assertEqual('bob@example.com', command.send_to)

    def _send(self, mailout_dir, extra_args, taynac=None):
        mock_app = Mock()
        mock_app.client_manager = fakes.make_fake_clients(
            taynac=taynac or Mock()
        )
        command = mailout.Send(mock_app, Mock())
        parser = command.get_parser("send")
        args = ['--mailout-dir', mailout_dir, '--confirm'] + extra_args
        out = self.capture_stdout()
        command.take_action(parser.parse_args(args))
        return command, out.getvalue()

    def _write_notification(self, mailout_dir, seqno, key, **overrides):
        notification = {
            'SeqNo': seqno,
            'Key': key,
            'Subject': f'Subject {key}',
            'Body': f'Body {key}',
            'SendTo': [f'{key}@example.com'],
            'Context': {'project_name': key},
        }
        notification.update(overrides)
        path = os.path.join(mailout_dir, f'notification@{key}')
        with open(path, 'w') as f:
            yaml.dump(notification, f, default_flow_style=False)
        return notification

    def test_send_limit(self):
        mock_taynac = Mock()
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            command, output = self._send(
                mailout_dir, ['--limit', '1'], taynac=mock_taynac
            )
            self.assertIn(
                'Sending notifications starting at sequence no 0', output
            )
            self.assertIn('Sent 1 notifications affecting 2 users', output)
            mock_taynac.messages.send.assert_called_once_with(
                subject='To change',
                body=ANY,
                recipient='fred.nurke@gmail.com',
                cc=['terry.towling@gmail.com'],
            )
            with open(os.path.join(mailout_dir, 'LAST_SENT')) as f:
                self.assertEqual('0', f.readline())

            # The next batch resumes where we left off
            mock_taynac.messages.send.reset_mock()
            command, output = self._send(
                mailout_dir, ['--limit', '1', '--resume'], taynac=mock_taynac
            )
            self.assertIn('Resuming notifications at sequence no 1', output)
            mock_taynac.messages.send.assert_called_once_with(
                subject='To change',
                body=ANY,
                recipient='randy.katz@gmail.com',
                cc=[],
            )
            with open(os.path.join(mailout_dir, 'LAST_SENT')) as f:
                self.assertEqual('1', f.readline())

    def test_send_already_sent(self):
        mock_taynac = Mock()
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            self._send(mailout_dir, [], taynac=mock_taynac)
            self.assertEqual(2, mock_taynac.messages.send.call_count)
            mock_taynac.messages.send.reset_mock()
            for extra_args in [[], ['--resume']]:
                with self.assertRaisesRegex(
                    Exception, 'notifications have already been sent'
                ):
                    self._send(mailout_dir, extra_args, taynac=mock_taynac)
            mock_taynac.messages.send.assert_not_called()

    def test_send_redirected_output(self):
        mock_taynac = Mock()
        with temp_workdir() as test_workdir:
            mailout_dir = self._prep(test_workdir)
            command, output = self._send(
                mailout_dir,
                ['--send-to', 'bob@example.com'],
                taynac=mock_taynac,
            )
            self.assertIn(
                'Redirecting all 2 notifications to bob@example.com', output
            )
            self.assertNotIn('CAUTION', output)
            self.assertIn('Sent 2 notifications affecting 3 users', output)

    def test_send_skips_removed_notification(self):
        """An operator can remove a notification file from the mailout
        dir before sending; the gap in the sequence numbers is skipped.
        """
        mock_taynac = Mock()
        with temp_workdir() as mailout_dir:
            self._write_notification(mailout_dir, 0, 'zero')
            self._write_notification(mailout_dir, 1, 'one')
            self._write_notification(mailout_dir, 2, 'two')
            os.remove(os.path.join(mailout_dir, 'notification@one'))
            command, output = self._send(mailout_dir, [], taynac=mock_taynac)
            sent = [
                call.kwargs['recipient']
                for call in mock_taynac.messages.send.call_args_list
            ]
            self.assertIn('zero@example.com', sent)
            self.assertNotIn('one@example.com', sent)

    def test_send_failure_reports_sequence_no(self):
        mock_taynac = Mock()
        mock_taynac.messages.send.side_effect = [None, BadRequest]
        with temp_workdir() as mailout_dir:
            self._write_notification(mailout_dir, 0, 'zero')
            self._write_notification(mailout_dir, 1, 'one')
            out = self.capture_stdout()
            with self.assertRaises(BadRequest):
                self._send(mailout_dir, [], taynac=mock_taynac)
            self.assertIn(
                'Failed while processing notification with sequence no 1',
                out.getvalue(),
            )
            # The tally is printed even on failure
            self.assertIn(
                'Sent 1 notifications affecting 1 users', out.getvalue()
            )
            with open(os.path.join(mailout_dir, 'LAST_SENT')) as f:
                self.assertEqual('0', f.readline())

    def test_send_notification(self):
        mock_taynac = Mock()
        with temp_workdir() as mailout_dir:
            command = mailout.Send(Mock(), Mock())
            command.taynac = mock_taynac
            command.send_to = None
            command.last_sent_pathname = os.path.join(mailout_dir, 'LAST_SENT')
            notification = {
                'SeqNo': 7,
                'Subject': 'Subject',
                'Body': 'Body',
                'SendTo': ['a@example.com', 'b@example.com', 'c@example.com'],
            }
            command.send_notification(notification)
            # The first recipient gets the message, the rest are cc'd
            mock_taynac.messages.send.assert_called_once_with(
                subject='Subject',
                body='Body',
                recipient='a@example.com',
                cc=['b@example.com', 'c@example.com'],
            )
            with open(command.last_sent_pathname) as f:
                self.assertEqual('7', f.read())

            # Redirected: single recipient, LAST_SENT untouched
            mock_taynac.messages.send.reset_mock()
            os.remove(command.last_sent_pathname)
            command.send_to = 'bob@example.com'
            command.send_notification(notification)
            mock_taynac.messages.send.assert_called_once_with(
                subject='Subject',
                body='Body',
                recipient='bob@example.com',
                cc=[],
            )
            self.assertFalse(os.path.exists(command.last_sent_pathname))

    def test_send_notification_empty(self):
        command = mailout.Send(Mock(), Mock())
        command.taynac = Mock()
        command.send_to = None
        notification = {
            'SeqNo': 0,
            'Subject': '',
            'Body': 'Body',
            'SendTo': ['a'],
        }
        with self.assertRaisesRegex(Exception, 'subject is empty'):
            command.send_notification(notification)
        notification = {
            'SeqNo': 0,
            'Subject': 'Subject',
            'Body': '',
            'SendTo': ['a'],
        }
        with self.assertRaisesRegex(Exception, 'body is empty'):
            command.send_notification(notification)
        command.taynac.messages.send.assert_not_called()

    def test_load_notifications(self):
        with temp_workdir() as mailout_dir:
            command = mailout.Send(Mock(), Mock())
            command.mailout_dir = mailout_dir
            command.last_sent_pathname = os.path.join(mailout_dir, 'LAST_SENT')
            # Nothing there yet
            self.assertEqual(({}, None), command.load_notifications())

            zero = self._write_notification(mailout_dir, 0, 'zero')
            two = self._write_notification(mailout_dir, 2, 'two')
            # Other files in the directory are ignored
            with open(os.path.join(mailout_dir, 'instances.list'), 'w') as f:
                f.write('id-1\n')
            self.assertEqual(
                ({0: zero, 2: two}, None), command.load_notifications()
            )

            with open(command.last_sent_pathname, 'w') as f:
                f.write('2')
            self.assertEqual(
                ({0: zero, 2: two}, 2), command.load_notifications()
            )


class TestGenerator(test.TestCase):
    def test_render_subject(self):
        with temp_template_file(TEST_TEMPLATE) as template:
            generator = mailout.Generator(
                template, '  Hello {{ project_name }} '
            )
            self.assertEqual(
                'Hello area54',
                generator.render_subject({'project_name': 'area54'}),
            )

    def test_render_template(self):
        with temp_template_file(TEST_TEMPLATE) as template:
            generator = mailout.Generator(template, 'subject')
            start_ts = datetime.datetime(2015, 6, 25, 9, 0)
            end_ts = datetime.datetime(2015, 6, 26, 11, 30)
            context = {
                'start_ts': start_ts,
                'end_ts': end_ts,
                'tz': 'AEST',
                'instances': ['i-1'],
            }
            self.assertEqual(
                'days: 1\n'
                'hours: 2\n'
                'start_ts: 2015-06-25 09:00:00\n'
                'end_ts: 2015-06-26 11:30:00\n'
                'tz: AEST\n'
                "instances: ['i-1']",
                generator.render_template(context),
            )

    def test_refine_context(self):
        with temp_template_file(TEST_TEMPLATE) as template:
            generator = mailout.Generator(template, 'subject')
            context = {
                'start_ts': datetime.datetime(2015, 6, 25, 9, 0),
                'end_ts': datetime.datetime(2015, 6, 25, 9, 30),
            }
            generator.refine_context(context)
            self.assertEqual(0, context['days'])
            self.assertEqual(0, context['hours'])

            context = {
                'start_ts': datetime.datetime(2015, 6, 25, 9, 0),
                'end_ts': datetime.datetime(2015, 6, 28, 8, 0),
            }
            generator.refine_context(context)
            self.assertEqual(2, context['days'])
            self.assertEqual(23, context['hours'])

            # Both timestamps are needed
            for context in [
                {},
                {'start_ts': datetime.datetime(2015, 6, 25, 9, 0)},
                {'end_ts': datetime.datetime(2015, 6, 25, 9, 0)},
            ]:
                original = dict(context)
                generator.refine_context(context)
                self.assertEqual(original, context)

    def test_undefined_variables(self):
        """Templates must not silently render missing variables"""
        with temp_template_file('{{ missing }}') as template:
            generator = mailout.Generator(template, '{{ also_missing }}')
            with self.assertRaises(UndefinedError):
                generator.render_template({})
            with self.assertRaises(UndefinedError):
                generator.render_subject({})

    def test_trim_blocks(self):
        with temp_template_file(
            '{% if affected > 1 %}\nmany\n{% else %}\none\n{% endif %}\n'
        ) as template:
            generator = mailout.Generator(template, 'subject')
            self.assertEqual(
                'many', generator.render_template({'affected': 2})
            )
            self.assertEqual('one', generator.render_template({'affected': 1}))

    def test_template_not_found(self):
        with temp_workdir() as workdir:
            with self.assertRaises(TemplateNotFound):
                mailout.Generator(os.path.join(workdir, 'no.tmpl'), 'subject')

    def test_shipped_templates(self):
        """The templates shipped with the package render with the
        context that the Instances command provides.
        """
        template_dir = os.path.join(
            os.path.dirname(mailout.__file__), 'templates'
        )
        templates = sorted(
            f for f in os.listdir(template_dir) if f.endswith('.tmpl')
        )
        self.assertTrue(templates)
        start_ts = datetime.datetime(
            2015, 6, 25, 9, 0, tzinfo=datetime.timezone.utc
        )
        context = {
            'project_name': 'area54',
            'affected': 2,
            'start_ts': start_ts,
            'end_ts': start_ts + datetime.timedelta(hours=3),
            'tz': 'UTC',
            'zones': ['danger'],
            'instances': [INSTANCE_1, INSTANCE_2],
            'recipients': ['fred.nurke@gmail.com'],
        }
        for name in templates:
            generator = mailout.Generator(
                os.path.join(template_dir, name),
                mailout.Instances.default_subject,
            )
            body = generator.render_template(dict(context))
            self.assertTrue(body, name)
            self.assertEqual(
                'Important announcement about project area54 instances',
                generator.render_subject(dict(context)),
            )
