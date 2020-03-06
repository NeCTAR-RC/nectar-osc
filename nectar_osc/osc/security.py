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
from oslo_config import cfg

from nectar_osc import security


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


class LockInstance(command.Command):
    """pause and lock an instance"""

    log = logging.getLogger(__name__ + '.Security.LockInstance')

    def get_parser(self, prog_name):
        parser = super(LockInstance, self).get_parser(prog_name)
        parser.add_argument(
            '--no-dry-run',
            metavar='',
            help=('Really lock the instance')
        )
        parser.add_argument(
            'id',
            metavar='<instance_id>',
            help=('Instance id to lock')
            )
        parser.add_argument(
            '--cc',
            metavar='<email>',
            help=('Extra email address to add to cc list')
            )
        
        print(parser.prog)
        return parser

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        config = get_config()
        return security.lockinstance(self.app.client_manager,
                                     parsed_args, config)


class UnlockInstance(command.Command):
    """unlock an instance"""

    log = logging.getLogger(__name__ + '.Security.UnlockInstance')

    def get_parser(self, prog_name):
        parser = super(UnlockInstance, self).get_parser(prog_name)
        parser.add_argument(
            '--no-dry-run',
            metavar='',
            help=('Really unlock the instance')
        )
        parser.add_argument(
            'id',
            metavar='<instance_id>',
            help=('Instance id to unlock')
            )
        
        print(parser.prog)
        return parser

    def take_action(self, parsed_args):
        self.log.debug('take_action(%s)', parsed_args)
        config = get_config()
        return security.unlockinstance(self.app.client_manager,
                                       parsed_args, config)

