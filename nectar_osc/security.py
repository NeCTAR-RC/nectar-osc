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
from nectar_osc import lister
from osc_lib.command import command
from oslo_config import cfg


try:
    from freshdesk.v2.api import API
except ImportError:
    API = None


def get_config():
    conf = cfg.CONF

    group = cfg.OptGroup('security')
    opts = [
        cfg.StrOpt('api_key'),
        cfg.StrOpt('email_config_id'),
        cfg.StrOpt('group_id'),
        cfg.StrOpt('domain'),
        ]

    conf.register_group(group)
    conf.register_opts(opts, group=group)
    conf([], project='nectar-osc',
         default_config_files=['~/.nectar.conf'])
    return(conf)


def get_freshdesk_config(api_key=None,
                         email_config_id=None,
                         group_id=None,
                         domain=None):
    """fetch freshdesk API details from config file"""
    msg = '\n'.join([
        'No Freshdesk details found in your config file.',
        '',
        'To find your Freshdesk API key by following the guide here:',
        'https://support.freshdesk.com/support/solutions/'
        'articles/215517-how-to-find-your-api-key',
        '',
        'Then add the following config to your configuration',
        'file (~/.nectar.conf):',
        '',
        '  [security]',
        '  api_key = <your api key>',
        '  email_config_id = <id>',
        '  group_id = <id>',
        '  domain = <domainname>',
    ])

    if api_key is None or email_config_id is None or \
        group_id is None or domain is None:
        print(msg)
        exit(1)

    fd_conf = {'api_key': api_key,
              'email_config_id': email_config_id,
              'group_id': group_id,
              'domain': domain}

    return(fd_conf)


def get_freshdesk_client(domain, api_key):
    if not API:
        print("To use this tool, you will need to also install the"
              "python-freshdesk package: \n"
              "  $ pip install python-freshdesk")
        exit(1)
    return API(domain, api_key)


def get_tenant_managers_emails(clients, instance):
    """Build a list of email addresses"""
    email_addresses = []
    project = clients.identity.projects.get(instance.tenant_id)
    role = clients.identity.roles.find(name='TenantManager')
    ras = clients.identity.role_assignments.list(project=project,
                                                role=role, include_names=True)
    for ra in ras:
        u = clients.identity.users.get(ra.user['id'])
        email_addresses.append(u.email)
    return email_addresses


def lockinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))


def unlockinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))


def deleteinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))


class SecurityCommand(command.Command):
    """security top class"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--no-dry-run',
            metavar='',
            help=('Really perform action')
        )
        parser.add_argument(
            'id',
            metavar='<instance_id>',
            help=('Instance uuid')
            )

        print(parser.prog)
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
        config = get_config()
        return lockinstance(self.app.client_manager,
                            parsed_args, config)


class UnlockInstance(SecurityCommand):
    """unlock an instance"""

    log = logging.getLogger(__name__ + '.Security.UnlockInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        config = get_config()
        return unlockinstance(self.app.client_manager,
                              parsed_args, config)


class DeleteInstance(SecurityCommand):
    """delete an instance"""

    log = logging.getLogger(__name__ + '.Security.DeleteInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        config = get_config()
        return deleteinstance(self.app.client_manager,
                              parsed_args, config)
