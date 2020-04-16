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
            '--no-dry-run',
            action='store_true',
            help=('Really perform action')
        )
        parser.add_argument(
            'id',
            metavar='<instance_id>',
            help=('Instance uuid')
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
            help=('Extra email address to add to cc list')
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
            print('Instance {} not found'.format(parsed_args.id))
            sys.exit(1)

        # Pause and lock instance
        if not parsed_args.no_dry_run:
            if instance.status != 'ACTIVE':
                print('Instance state {}, will not pause'.format(
                    instance.status))
            else:
                print('Would pause and lock instance {}'.format(instance.id))
        else:
            if instance.status != 'ACTIVE':
                print('Instance not in ACTIVE state ({}), skipping'
                      .format(instance.status))
            else:
                print('Pausing instance {}'.format(instance.id))
                instance.pause()

            print('Locking instance {}'.format(instance.id))
            instance.lock()

        # Process ticket
        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print('Found existing ticket: {}'.format(ticket_url))
            ticket_id = int(ticket_url.split('/')[-1])

            if not parsed_args.no_dry_run:
                print('Would set ticket #{} status to open/urgent'
                      .format(ticket_id))
            else:
                # Set ticket status, priority and reply
                print('Replying to ticket with action details')
                action = 'Instance <b>{} ({})</b> has been <b>paused and '\
                         'locked</b>'.format(instance.name, instance.id)
                fd.comments.create_reply(ticket_id, action)
                print('Setting ticket #{} status to open/urgent'.format(
                    ticket_id))
                fd.tickets.update_ticket(ticket_id, status=6, priority=4)
        else:
            project = clients.identity.projects.get(instance.tenant_id)
            user = clients.identity.users.get(instance.user_id)
            email = user.email or 'no-reply@nectar.org.au'
            name = getattr(user, 'full_name', email)
            cc_emails = identity.get_tenant_managers_emails(clients.identity,
                                                            instance)
            if(parsed_args.cc):
                cc_emails.append(parsed_args.cc)

            # Create ticket if none exist, and add instance info
            subject = 'Security incident for instance {} ({})'.format(
                instance.name, instance.id)
            body = '<br />\n'.join([
                'Dear Nectar Research Cloud User, ',
                '',
                '',
                'We have reason to believe that cloud instance: '
                '<b>{} ({})</b>'.format(instance.name, instance.id),
                'in the project <b>{}</b>'.format(project.name),
                'created by <b>{}</b>'.format(email),
                'has been involved in a security incident, ',
                'and has been locked.',
                '',
                'We have opened this helpdesk ticket to track the details ',
                'and the progress of the resolution of this issue.',
                '',
                'Please reply to this email if you have any questions or ',
                'concerns.',
                '',
                'Thanks, ',
                'Nectar Research Cloud Team'
            ])

            if not parsed_args.no_dry_run:
                print('Would create ticket with details:')
                print('  To:      {} <{}>'.format(name, email))
                print('  CC:      {}'.format(', '.join(cc_emails)))
                print('  Subject: {}'.format(subject))

                print('Would add instance details to ticket:')
                print(compute.show_instance(clients, instance.id))
                print(network.show_instance_security_groups(
                    clients, instance.id))
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
                    tags=['security'])
                ticket_id = ticket.id

                # Use friendly domain name if using prod
                if fd.domain == 'dhdnectar.freshdesk.com':
                    domain = 'support.ehelp.edu.au'
                else:
                    domain = fd.domain

                ticket_url = 'https://{}/helpdesk/tickets/{}'\
                             .format(domain, ticket_id)
                clients.compute.servers.set_meta(instance.id,
                                                 {'security_ticket':
                                                  ticket_url})
                print('Ticket #{} has been created: {}'
                      .format(ticket_id, ticket_url))

                # Add a private note with instance details
                print('Adding instance information to ticket')
                instance_info = compute.show_instance(
                    clients, instance.id, style='html')
                sg_info = network.show_instance_security_groups(
                    clients, instance.id, style='html')
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
            print('Instance {} not found'.format(parsed_args.id))
            sys.exit(1)

        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print('Found ticket: {}'.format(ticket_url))
            ticket_id = int(ticket_url.split('/')[-1])
        else:
            if parsed_args.no_dry_run is True:
                print('No ticket found in instance metadata!')
                sys.exit(1)

        if instance.status == 'PAUSED':
            if not parsed_args.no_dry_run:
                print('Would unpause and unlock instance {}'.format(
                    instance.id))
                print('Would reply to ticket')
                print('Would resolve ticket')
            else:
                print('Unpausing instance {}'.format(instance.id))
                instance.unpause()

                print('Unlocking instance {}'.format(instance.id))
                instance.unlock()

                # Add reply to user
                print('Replying to ticket with action details')
                action = 'Instance <b>{} ({})</b> has been <b>unpaused and '\
                         'unlocked</b>'.format(instance.name, instance.id)
                fd.comments.create_reply(ticket_id, action)

                # Set ticket status=resolved
                print('Setting ticket #{} status to resolved'.format(
                    ticket_id))
                fd.tickets.update_ticket(ticket_id, status=4)
        else:
            print('Instance {} is not locked, wont unlock'.format(instance.id))


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
            print('Instance {} not found'.format(parsed_args.id))
            sys.exit(1)

        ticket_id = None
        ticket_url = instance.metadata.get('security_ticket')
        if ticket_url:
            print('Found ticket: {}'.format(ticket_url))
            ticket_id = int(ticket_url.split('/')[-1])
        else:
            if parsed_args.no_dry_run is True:
                print('No ticket found in instance metadata!')
                sys.exit(1)

        # DELETE!!!
        if instance.status == 'PAUSED':
            if not parsed_args.no_dry_run:
                print('Would delete instance {}'.format(instance.id))
                print('Would reply to ticket')
                print('Would resolve ticket')
            else:
                print('Deleting instance {})'.format(instance.id))
                instance.delete()

                # Add reply to user
                print('Updating ticket with action')
                action = 'Instance <b>{} ({})</b> has been <b>deleted.</b>'\
                         .format(instance.name, instance.id)
                fd.comments.create_reply(ticket_id, action)

                # Set ticket status=resolved
                print('Resolving ticket #{}'.format(ticket_id))
                fd.tickets.update_ticket(ticket_id, status=4)
        else:
            print('Instance {} is not locked, wont delete'.format(instance.id))
