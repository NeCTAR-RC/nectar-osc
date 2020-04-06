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

from nectar_osc import compute
from nectar_osc import network


class ShowCommand(command.Command):
    """show top class"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'id',
            metavar='<server>',
            help=('Server (name or ID)')
            )

        return parser


class ShowInstance(ShowCommand):
    """show instance details"""

    log = logging.getLogger(__name__ + '.Show.ShowInstance')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager

        try:
            instance = clients.compute.servers.get(parsed_args.id)
        except n_exc.NotFound:
            print('Server {} not found'.format(parsed_args.id))
            sys.exit(1)

        print(compute.show_instance(clients, instance.id))


class ShowSecuritygroups(ShowCommand):
    """show instance security group details"""

    log = logging.getLogger(__name__ + '.Show.ShowSecuritygroups')

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        clients = self.app.client_manager

        try:
            instance = clients.compute.servers.get(parsed_args.id)
        except n_exc.NotFound:
            print('Server {} not found'.format(parsed_args.id))
            sys.exit(1)

        print(network.show_instance_security_groups(
                    clients, instance.id))
