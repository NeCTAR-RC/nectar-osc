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

from unittest.mock import ANY
from unittest.mock import Mock
from unittest.mock import patch

from oslo_config import cfg

from nectar_osc import security
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


CONF = cfg.CONF

INSTANCE_ID = '00000000-1111-1111-1111-111111111112'
TICKET_URL = 'https://support.ehelp.edu.au/helpdesk/tickets/4242'

FRED = '33333333-1111-1111-1111-111111111111'
TROVE = '33333333-1111-1111-1111-111111111114'
AREA54 = '44444444-1111-1111-1111-111111111111'


def make_server(status='ACTIVE', metadata=None, user_id=FRED):
    """A fresh server in project area54 so tests can't interfere"""
    return fakes.FakeServer(
        id=INSTANCE_ID,
        name='two',
        status=status,
        flavor={'id': '11111111-1111-1111-1111-111111111111', 'name': 'lemon'},
        compute_host='cn1.danger.nectar.org.au',
        zone='danger',
        image={'id': '22222222-1111-1111-1111-111111111112'},
        metadata=metadata if metadata is not None else {},
        addresses={'net_name': [{'addr': '192.168.76.112'}]},
        user_id=user_id,
        project_id=AREA54,
    )


class SecurityTestCase(test.TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch('nectar_osc.security.freshdesk.get_client')
        self.fd = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.fd.domain = 'dhdnectar.freshdesk.com'
        self.fd.tickets.create_outbound_email.return_value.id = 4242

        patcher = patch('nectar_osc.security.compute.show_instance')
        self.mock_show_instance = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_show_instance.return_value = 'INSTANCE DETAILS'

        patcher = patch(
            'nectar_osc.security.network.show_instance_security_groups'
        )
        self.mock_show_sgs = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_show_sgs.return_value = 'SECURITY GROUPS'

    def _run(self, cls, argv, server):
        """Run the command against a fake cloud holding 'server'.

        The identity service is the fake one (so project, user and
        tenant manager lookups are real), the compute client is a Mock
        so that the actions taken on the instance can be checked.
        """
        clients = fakes.make_fake_clients()
        clients.compute = Mock()
        clients.compute.get_server.return_value = server
        command = cls(Mock(), Mock())
        command.app.client_manager = clients
        parsed_args = command.get_parser('test').parse_args(argv)
        out = self.capture_stdout()
        command.take_action(parsed_args)
        return clients, out.getvalue()

    def assertNoInstanceActions(self, compute):
        for action in [
            'pause_server',
            'lock_server',
            'unpause_server',
            'unlock_server',
            'delete_server',
            'set_server_metadata',
        ]:
            getattr(compute, action).assert_not_called()

    def assertNoTicketActions(self):
        self.fd.tickets.create_outbound_email.assert_not_called()
        self.fd.tickets.update_ticket.assert_not_called()
        self.fd.comments.create_reply.assert_not_called()
        self.fd.comments.create_note.assert_not_called()


class TestSecurityCommand(SecurityTestCase):
    def test_get_parser(self):
        for cls in [
            security.LockInstance,
            security.UnlockInstance,
            security.DeleteInstance,
        ]:
            command = cls(Mock(), Mock())
            parser = command.get_parser('security')
            args = parser.parse_args([INSTANCE_ID])
            self.assertEqual(INSTANCE_ID, args.id)
            self.assertFalse(args.no_dry_run)
            args = parser.parse_args(['--no-dry-run', INSTANCE_ID])
            self.assertTrue(args.no_dry_run)
            with self.assertRaises(SystemExit):
                parser.parse_args([])

    def test_lock_parser(self):
        command = security.LockInstance(Mock(), Mock())
        parser = command.get_parser('lock')
        args = parser.parse_args([INSTANCE_ID])
        self.assertIsNone(args.cc)
        args = parser.parse_args(['--cc', 'bob@example.com', INSTANCE_ID])
        self.assertEqual('bob@example.com', args.cc)


class TestLockInstance(SecurityTestCase):
    def test_dry_run_active_new_ticket(self):
        clients, output = self._run(
            security.LockInstance, [INSTANCE_ID], make_server()
        )
        clients.compute.get_server.assert_called_once_with(INSTANCE_ID)
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(
            'Running in dry-run mode (use --no-dry-run to action)', output
        )
        self.assertIn(f'Would pause and lock instance {INSTANCE_ID}', output)
        self.assertIn('Would create ticket with details:', output)
        self.assertIn('  To:      Fred Nurke <fred.nurke@gmail.com>', output)
        self.assertIn('  CC:      fred.nurke@gmail.com', output)
        self.assertIn(
            f'  Subject: Security incident for instance two ({INSTANCE_ID})',
            output,
        )
        self.assertIn('Would add instance details to ticket:', output)
        self.assertIn('INSTANCE DETAILS\nSECURITY GROUPS', output)
        self.mock_show_instance.assert_called_once_with(clients, INSTANCE_ID)
        self.mock_show_sgs.assert_called_once_with(clients, INSTANCE_ID)

    def test_dry_run_not_active(self):
        clients, output = self._run(
            security.LockInstance, [INSTANCE_ID], make_server(status='SHUTOFF')
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn('Instance state SHUTOFF, will not pause', output)
        self.assertNotIn('Would pause', output)
        # The ticket would still be created
        self.assertIn('Would create ticket with details:', output)

    def test_dry_run_existing_ticket(self):
        clients, output = self._run(
            security.LockInstance,
            [INSTANCE_ID],
            make_server(metadata={'security_ticket': TICKET_URL}),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(f'Found existing ticket: {TICKET_URL}', output)
        self.assertIn('Would set ticket #4242 status to open/urgent', output)
        self.assertNotIn('Would create ticket', output)

    def test_lock_active_new_ticket(self):
        server = make_server()
        clients, output = self._run(
            security.LockInstance, ['--no-dry-run', INSTANCE_ID], server
        )
        self.assertNotIn('dry-run', output)
        clients.compute.pause_server.assert_called_once_with(server)
        clients.compute.lock_server.assert_called_once_with(server)
        self.assertIn(f'Pausing instance {INSTANCE_ID}', output)
        self.assertIn(f'Locking instance {INSTANCE_ID}', output)

        self.assertIn('Creating new Freshdesk ticket', output)
        self.fd.tickets.create_outbound_email.assert_called_once_with(
            name='Fred Nurke',
            description=ANY,
            subject=f'Security incident for instance two ({INSTANCE_ID})',
            email='fred.nurke@gmail.com',
            cc_emails=['fred.nurke@gmail.com'],
            email_config_id=CONF.freshdesk.email_config_id,
            group_id=CONF.freshdesk.group_id,
            priority=4,
            status=2,
            tags=['security'],
        )
        body = self.fd.tickets.create_outbound_email.call_args.kwargs[
            'description'
        ]
        self.assertIn('Dear Nectar Research Cloud User, <br />\n', body)
        self.assertIn(f'<b>two ({INSTANCE_ID})</b>', body)
        self.assertIn('in the project <b>area54</b>', body)
        self.assertIn('created by <b>fred.nurke@gmail.com</b>', body)

        # Production freshdesk domain is mapped to the friendly one
        clients.compute.set_server_metadata.assert_called_once_with(
            INSTANCE_ID, security_ticket=TICKET_URL
        )
        self.assertIn(f'Ticket #4242 has been created: {TICKET_URL}', output)

        self.assertIn('Adding instance information to ticket', output)
        self.mock_show_instance.assert_called_once_with(
            clients, INSTANCE_ID, style='html'
        )
        self.mock_show_sgs.assert_called_once_with(
            clients, INSTANCE_ID, style='html'
        )
        self.fd.comments.create_note.assert_called_once_with(
            4242, 'INSTANCE DETAILS<br/><br/>SECURITY GROUPS'
        )
        self.fd.tickets.update_ticket.assert_not_called()
        self.fd.comments.create_reply.assert_not_called()

    def test_lock_not_active(self):
        server = make_server(status='SHUTOFF')
        clients, output = self._run(
            security.LockInstance, ['--no-dry-run', INSTANCE_ID], server
        )
        clients.compute.pause_server.assert_not_called()
        clients.compute.lock_server.assert_called_once_with(server)
        self.assertIn(
            'Instance not in ACTIVE state (SHUTOFF), skipping', output
        )
        self.assertIn(f'Locking instance {INSTANCE_ID}', output)
        self.fd.tickets.create_outbound_email.assert_called_once()

    def test_lock_existing_ticket(self):
        server = make_server(metadata={'security_ticket': TICKET_URL})
        clients, output = self._run(
            security.LockInstance, ['--no-dry-run', INSTANCE_ID], server
        )
        clients.compute.pause_server.assert_called_once_with(server)
        clients.compute.lock_server.assert_called_once_with(server)
        self.assertIn(f'Found existing ticket: {TICKET_URL}', output)
        self.assertIn('Replying to ticket with action details', output)
        self.fd.comments.create_reply.assert_called_once_with(
            4242,
            f'Instance <b>two ({INSTANCE_ID})</b> has been '
            '<b>paused and locked</b>',
        )
        self.assertIn('Setting ticket #4242 status to open/urgent', output)
        self.fd.tickets.update_ticket.assert_called_once_with(
            4242, status=6, priority=4
        )
        self.fd.tickets.create_outbound_email.assert_not_called()
        self.fd.comments.create_note.assert_not_called()
        clients.compute.set_server_metadata.assert_not_called()

    def test_lock_non_production_domain(self):
        self.fd.domain = 'test.freshdesk.com'
        clients, output = self._run(
            security.LockInstance, ['--no-dry-run', INSTANCE_ID], make_server()
        )
        url = 'https://test.freshdesk.com/helpdesk/tickets/4242'
        clients.compute.set_server_metadata.assert_called_once_with(
            INSTANCE_ID, security_ticket=url
        )
        self.assertIn(f'Ticket #4242 has been created: {url}', output)

    def test_lock_cc(self):
        clients, output = self._run(
            security.LockInstance,
            ['--no-dry-run', '--cc', 'bob@example.com', INSTANCE_ID],
            make_server(),
        )
        self.fd.tickets.create_outbound_email.assert_called_once()
        self.assertEqual(
            ['fred.nurke@gmail.com', 'bob@example.com'],
            self.fd.tickets.create_outbound_email.call_args.kwargs[
                'cc_emails'
            ],
        )

    def test_dry_run_cc(self):
        clients, output = self._run(
            security.LockInstance,
            ['--cc', 'bob@example.com', INSTANCE_ID],
            make_server(),
        )
        self.assertIn(
            '  CC:      fred.nurke@gmail.com, bob@example.com', output
        )

    def test_lock_user_without_email(self):
        """Users without an email get the no-reply address"""
        clients, output = self._run(
            security.LockInstance,
            ['--no-dry-run', INSTANCE_ID],
            make_server(user_id=TROVE),
        )
        self.fd.tickets.create_outbound_email.assert_called_once()
        kwargs = self.fd.tickets.create_outbound_email.call_args.kwargs
        self.assertEqual('no-reply@nectar.org.au', kwargs['email'])
        self.assertEqual('Trove Service', kwargs['name'])
        self.assertIn(
            'created by <b>no-reply@nectar.org.au</b>', kwargs['description']
        )

    def test_dry_run_user_without_full_name(self):
        fred = fakes.FakeUser(
            id=FRED, name='fred', email='fred@example.com', full_name=None
        )
        # A user object without a full_name attribute at all
        del fred.full_name
        clients = fakes.make_fake_clients(users=[fred] + fakes.USERS[1:])
        clients.compute = Mock()
        clients.compute.get_server.return_value = make_server()
        command = security.LockInstance(Mock(), Mock())
        command.app.client_manager = clients
        out = self.capture_stdout()
        command.take_action(
            command.get_parser('lock').parse_args([INSTANCE_ID])
        )
        self.assertIn(
            '  To:      fred@example.com <fred@example.com>', out.getvalue()
        )


class TestUnlockInstance(SecurityTestCase):
    def test_dry_run_paused(self):
        clients, output = self._run(
            security.UnlockInstance,
            [INSTANCE_ID],
            make_server(
                status='PAUSED', metadata={'security_ticket': TICKET_URL}
            ),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(
            'Running in dry-run mode (use --no-dry-run to action)', output
        )
        self.assertIn(f'Found ticket: {TICKET_URL}', output)
        self.assertIn(
            f'Would unpause and unlock instance {INSTANCE_ID}', output
        )
        self.assertIn('Would reply to ticket', output)
        self.assertIn('Would resolve ticket', output)

    def test_dry_run_paused_without_ticket(self):
        """Without a ticket, a dry run still shows what would happen"""
        clients, output = self._run(
            security.UnlockInstance,
            [INSTANCE_ID],
            make_server(status='PAUSED'),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNotIn('Found ticket', output)
        self.assertIn(
            f'Would unpause and unlock instance {INSTANCE_ID}', output
        )

    def test_dry_run_not_paused(self):
        clients, output = self._run(
            security.UnlockInstance,
            [INSTANCE_ID],
            make_server(metadata={'security_ticket': TICKET_URL}),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn("Instance 4242 is not locked, won't unlock", output)

    def test_unlock(self):
        server = make_server(
            status='PAUSED', metadata={'security_ticket': TICKET_URL}
        )
        clients, output = self._run(
            security.UnlockInstance, ['--no-dry-run', INSTANCE_ID], server
        )
        self.assertNotIn('dry-run', output)
        clients.compute.unpause_server.assert_called_once_with(server)
        clients.compute.unlock_server.assert_called_once_with(server)
        clients.compute.delete_server.assert_not_called()
        self.assertIn(f'Unpausing instance {INSTANCE_ID}', output)
        self.assertIn(f'Unlocking instance {INSTANCE_ID}', output)
        self.assertIn('Replying to ticket with action details', output)
        self.fd.comments.create_reply.assert_called_once_with(
            4242,
            f'Instance <b>two ({INSTANCE_ID})</b> has been '
            '<b>unpaused and unlocked</b>',
        )
        self.assertIn('Setting ticket #4242 status to resolved', output)
        self.fd.tickets.update_ticket.assert_called_once_with(4242, status=4)

    def test_unlock_not_paused(self):
        clients, output = self._run(
            security.UnlockInstance,
            ['--no-dry-run', INSTANCE_ID],
            make_server(metadata={'security_ticket': TICKET_URL}),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn("Instance 4242 is not locked, won't unlock", output)

    def test_unlock_without_ticket(self):
        out = self.capture_stdout()
        with self.assertRaises(SystemExit) as cm:
            self._run(
                security.UnlockInstance,
                ['--no-dry-run', INSTANCE_ID],
                make_server(status='PAUSED'),
            )
        self.assertEqual(1, cm.exception.code)
        self.assertIn('No ticket found in instance metadata!', out.getvalue())
        self.assertNoTicketActions()


class TestDeleteInstance(SecurityTestCase):
    def test_dry_run_paused(self):
        clients, output = self._run(
            security.DeleteInstance,
            [INSTANCE_ID],
            make_server(
                status='PAUSED', metadata={'security_ticket': TICKET_URL}
            ),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(
            'Running in dry-run mode (use --no-dry-run to action)', output
        )
        self.assertIn(f'Found ticket: {TICKET_URL}', output)
        self.assertIn(f'Would delete instance {INSTANCE_ID}', output)
        self.assertIn('Would reply to ticket', output)
        self.assertIn('Would resolve ticket', output)

    def test_dry_run_paused_without_ticket(self):
        clients, output = self._run(
            security.DeleteInstance,
            [INSTANCE_ID],
            make_server(status='PAUSED'),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNotIn('Found ticket', output)
        self.assertIn(f'Would delete instance {INSTANCE_ID}', output)

    def test_dry_run_not_paused(self):
        clients, output = self._run(
            security.DeleteInstance,
            [INSTANCE_ID],
            make_server(metadata={'security_ticket': TICKET_URL}),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(
            f"Instance {INSTANCE_ID} is not locked, won't delete", output
        )

    def test_delete(self):
        server = make_server(
            status='PAUSED', metadata={'security_ticket': TICKET_URL}
        )
        clients, output = self._run(
            security.DeleteInstance, ['--no-dry-run', INSTANCE_ID], server
        )
        self.assertNotIn('dry-run', output)
        clients.compute.delete_server.assert_called_once_with(server)
        clients.compute.unpause_server.assert_not_called()
        clients.compute.unlock_server.assert_not_called()
        self.assertIn(f'Deleting instance {INSTANCE_ID}', output)
        self.assertIn('Updating ticket with action', output)
        self.fd.comments.create_reply.assert_called_once_with(
            4242,
            f'Instance <b>two ({INSTANCE_ID})</b> has been <b>deleted.</b>',
        )
        self.assertIn('Resolving ticket #4242', output)
        self.fd.tickets.update_ticket.assert_called_once_with(4242, status=4)

    def test_delete_not_paused(self):
        """Only paused (i.e. locked) instances get deleted"""
        clients, output = self._run(
            security.DeleteInstance,
            ['--no-dry-run', INSTANCE_ID],
            make_server(metadata={'security_ticket': TICKET_URL}),
        )
        self.assertNoInstanceActions(clients.compute)
        self.assertNoTicketActions()
        self.assertIn(
            f"Instance {INSTANCE_ID} is not locked, won't delete", output
        )

    def test_delete_without_ticket(self):
        out = self.capture_stdout()
        with self.assertRaises(SystemExit) as cm:
            self._run(
                security.DeleteInstance,
                ['--no-dry-run', INSTANCE_ID],
                make_server(status='PAUSED'),
            )
        self.assertEqual(1, cm.exception.code)
        self.assertIn('No ticket found in instance metadata!', out.getvalue())
        self.assertNoTicketActions()
