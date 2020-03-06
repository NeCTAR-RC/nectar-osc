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
from nectar_osc import compute
from nectar_osc import config
from nectar_osc import freshdesk
from nectar_osc import identity
from nectar_osc import network
from osc_lib.command import command
from oslo_config import cfg


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
        conf = config.get_config()

        instance = clients.compute.servers.get(parsed_args.id)
        print(compute.show_instance(clients, instance.id))
        print(network.show_sg_groups(clients, instance.id))
        return True


class UnlockInstance(SecurityCommand):
    """unlock an instance"""

    log = logging.getLogger(__name__ + '.Security.UnlockInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager
        conf = config.get_config()

        instance = clients.compute.servers.get(parsed_args.id)
        print(compute.show_instance(clients, instance.id))
        print(network.show_sg_groups(clients, instance.id))
        return True


class DeleteInstance(SecurityCommand):
    """delete an instance"""

    log = logging.getLogger(__name__ + '.Security.DeleteInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager
        conf = config.get_config()

        instance = clients.compute.servers.get(parsed_args.id)
        print(compute.show_instance(clients, instance.id))
        print(network.show_sg_groups(clients, instance.id))
        return True
