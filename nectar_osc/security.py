#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import logging
import sys

from novaclient import exceptions as n_exc
from osc_lib.command import command
from oslo_config import cfg

from nectar_osc import compute
from nectar_osc import freshdesk
from nectar_osc import identity
from nectar_osc import network


CONF = cfg.CONF


class SecurityCommand(command.Command):
    """security top class"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--no-dry-run', action='store_true', help=('Really perform action')
        )
        parser.add_argument(
            'id', metavar='<instance_id>', help=('Instance uuid')
        )

        return parser


class LockInstance(SecurityCommand):
    """pause and lock an instance"""

    log = logging.getLogger(__name__ + '.Security.LockInstance')

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--cc',
            metavar='<email>',
            help=('Extra email address to add to cc list'),
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager

        fd = freshdesk.get_client()

        if not parsed_args.no_dry_run:
            print('Running in dry-run mode (use --no-dry-run to action)')

        try:
            instance = clients.compute.servers.get(parsed_args.id)
        except n_exc.NotFound:
            print(f'Instance {parsed_args.id} not found')
            sys.exit(1)

        # Pause and lock instance
        if not parsed_args.no_dry_run:
            if instance.status != 'ACTIVE':
                print(f'Instance state {instance.status}, will not pause')
            else:
                print(f'Would pause and lock instance {instance.id}')
        else:
            if instance.status != 'ACTIVE':
                print(
                    f'Instance not in ACTIVE state ({instance.status}), '
                    'skipping'
                )
            else:
                print(f'Pausing instance {instance.id}')
                instance.pause()

            print(f'Locking instance {instance.id}')
            instance.lock()

        # Process ticket
        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print(f'Found existing ticket: {ticket_url}')
            ticket_id = int(ticket_url.split('/')[-1])

            if not parsed_args.no_dry_run:
                print(f'Would set ticket #{ticket_id} status to open/urgent')
            else:
                # Set ticket status, priority and reply
                print('Replying to ticket with action details')
                action = (
                    f'Instance <b>{instance.name} ({instance.id})</b>'
                    ' has been <b>paused and '
                    'locked</b>'
                )
                fd.comments.create_reply(ticket_id, action)
                print(f'Setting ticket #{ticket_id} status to open/urgent')
                fd.tickets.update_ticket(ticket_id, status=6, priority=4)
        else:
            project = clients.identity.projects.get(instance.tenant_id)
            user = clients.identity.users.get(instance.user_id)
            email = user.email or 'no-reply@nectar.org.au'
            name = getattr(user, 'full_name', email)
            cc_emails = identity.get_tenant_managers_emails(
                clients.identity, instance
            )
            if parsed_args.cc:
                cc_emails.append(parsed_args.cc)

            # Create ticket if none exist, and add instance info
            subject = (
                f'Security incident for instance {instance.name} '
                f'({instance.id})'
            )
            body = '<br />\n'.join(
                [
                    'Dear Nectar Research Cloud User, ',
                    '',
                    '',
                    'We have reason to believe that cloud instance: '
                    f'<b>{instance.name} ({instance.id})</b>',
                    f'in the project <b>{project.name}</b>',
                    f'created by <b>{email}</b>',
                    'has been involved in a security incident, ',
                    'and has been locked.',
                    '',
                    'We have opened this helpdesk ticket to track the ',
                    'details and the progress of the resolution of this ',
                    'issue.',
                    '',
                    'Please reply to this email if you have any questions or ',
                    'concerns.',
                    '',
                    'Thanks, ',
                    'Nectar Research Cloud Team',
                ]
            )

            if not parsed_args.no_dry_run:
                print('Would create ticket with details:')
                print(f'  To:      {name} <{email}>')
                print(f'  CC:      {", ".join(cc_emails)}')
                print(f'  Subject: {subject}')

                print('Would add instance details to ticket:')
                print(compute.show_instance(clients, instance.id))
                print(
                    network.show_instance_security_groups(clients, instance.id)
                )
            else:
                print('Creating new Freshdesk ticket')
                ticket = fd.tickets.create_outbound_email(
                    name=name,
                    description=body,
                    subject=subject,
                    email=email,
                    cc_emails=cc_emails,
                    email_config_id=CONF.freshdesk.email_config_id,
                    group_id=CONF.freshdesk.group_id,
                    priority=4,
                    status=2,
                    tags=['security'],
                )
                ticket_id = ticket.id

                # Use friendly domain name if using prod
                if fd.domain == 'dhdnectar.freshdesk.com':
                    domain = 'support.ehelp.edu.au'
                else:
                    domain = fd.domain

                ticket_url = f'https://{domain}/helpdesk/tickets/{ticket_id}'
                clients.compute.servers.set_meta(
                    instance.id, {'security_ticket': ticket_url}
                )
                print(f'Ticket #{ticket_id} has been created: {ticket_url}')

                # Add a private note with instance details
                print('Adding instance information to ticket')
                instance_info = compute.show_instance(
                    clients, instance.id, style='html'
                )
                sg_info = network.show_instance_security_groups(
                    clients, instance.id, style='html'
                )
                body = '<br/><br/>'.join([instance_info, sg_info])
                fd.comments.create_note(ticket_id, body)


class UnlockInstance(SecurityCommand):
    """unlock an instance"""

    log = logging.getLogger(__name__ + '.Security.UnlockInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager

        fd = freshdesk.get_client()

        """unlock an instance"""
        if not parsed_args.no_dry_run:
            print('Running in dry-run mode (use --no-dry-run to action)')

        try:
            instance = clients.compute.servers.get(parsed_args.id)
        except n_exc.NotFound:
            print(f'Instance {parsed_args.id} not found')
            sys.exit(1)

        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print(f'Found ticket: {ticket_url}')
            ticket_id = int(ticket_url.split('/')[-1])
        else:
            if parsed_args.no_dry_run is True:
                print('No ticket found in instance metadata!')
                sys.exit(1)

        if instance.status == 'PAUSED':
            if not parsed_args.no_dry_run:
                print(f'Would unpause and unlock instance {instance.id}')
                print('Would reply to ticket')
                print('Would resolve ticket')
            else:
                print(f'Unpausing instance {instance.id}')
                instance.unpause()

                print(f'Unlocking instance {instance.id}')
                instance.unlock()

                # Add reply to user
                print('Replying to ticket with action details')
                action = (
                    f'Instance <b>{instance.name} ({instance.id})</b>'
                    ' has been <b>unpaused and unlocked</b>'
                )
                fd.comments.create_reply(ticket_id, action)

                # Set ticket status=resolved
                print(f'Setting ticket #{ticket_id} status to resolved')
                fd.tickets.update_ticket(ticket_id, status=4)
        else:
            print(f"Instance {ticket_id} is not locked, won't unlock")


class DeleteInstance(SecurityCommand):
    """delete an instance"""

    log = logging.getLogger(__name__ + '.Security.DeleteInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager

        fd = freshdesk.get_client()

        """delete an instance"""
        if not parsed_args.no_dry_run:
            print('Running in dry-run mode (use --no-dry-run to action)')

        try:
            instance = clients.compute.servers.get(parsed_args.id)
        except n_exc.NotFound:
            print(f'Instance {parsed_args.id} not found')
            sys.exit(1)

        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print(f'Found ticket: {ticket_url}')
            ticket_id = int(ticket_url.split('/')[-1])
        else:
            if parsed_args.no_dry_run is True:
                print('No ticket found in instance metadata!')
                sys.exit(1)

        # DELETE!!!
        if instance.status == 'PAUSED':
            if not parsed_args.no_dry_run:
                print(f'Would delete instance {instance.id}')
                print('Would reply to ticket')
                print('Would resolve ticket')
            else:
                print(f'Deleting instance {instance.id})')
                instance.delete()

                # Add reply to user
                print('Updating ticket with action')
                action = (
                    f'Instance <b>{instance.name} ({instance.id})</b>'
                    ' has been <b>deleted.</b>'
                )
                fd.comments.create_reply(ticket_id, action)

                # Set ticket status=resolved
                print(f'Resolving ticket #{ticket_id}')
                fd.tickets.update_ticket(ticket_id, status=4)
        else:
            print(f"Instance {instance.id} is not locked, won't delete")
