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

from osc_lib.command import command
from osc_lib import utils as osc_utils
from oslo_config import cfg


CONF = cfg.CONF


class ListFlavors(command.Lister):
    """List Flavors with rating."""

    log = logging.getLogger(__name__ + '.ListFlavors')

    def get_parser(self, prog_name):
        parser = super(ListFlavors, self).get_parser(prog_name)
        parser.add_argument(
            '--all',
            action='store_true',
            help=('Display All flavors')
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        compute_client = self.app.client_manager.compute
        rating_client = self.app.client_manager.rating
        flavor_kwargs = {}
        if parsed_args.all:
            flavor_kwargs['is_public'] = None
        flavors = compute_client.flavors.list(**flavor_kwargs)
        groups = rating_client.rating.hashmap.get_group()['groups']
        group_id = None
        for g in groups:
            if g.get('name') == 'instance_uptime_flavor_id':
                group_id = g.get('group_id')
                break
        mappings = rating_client.rating.hashmap.get_group_mappings(
            group_id=group_id)['mappings']
        mappings = {m.get('value'): m.get('cost') for m in mappings}
        for f in flavors:
            f.rate = mappings.get(f.id)
        columns = ['id', 'name', 'rate']
        return (
            columns,
            (osc_utils.get_item_properties(f, columns) for f in flavors)
        )
