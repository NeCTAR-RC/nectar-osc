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

import sys

from oslo_config import cfg
from oslo_config import generator
from pathlib import Path


homedir = str(Path.home())
if not Path(homedir).exists():
    print('config dir {} doesnt exist'.format(homedir))
    sys.exit(1)


freshdesk_opts = [
    cfg.StrOpt('api_key', help='your freshdesk api key'),
    cfg.IntOpt('email_config_id', default='6000071619',
               help='freshdesk email config id'),
    cfg.IntOpt('group_id', default='6000208874',
               help='freshdesk group id'),
    cfg.StrOpt('domain', default='dhdnectar.freshdesk.com',
               help='freshdesk domain'),
]

cfg.CONF.register_opts(freshdesk_opts, group='freshdesk')


def list_opts():
    return [
        ('freshdesk', freshdesk_opts),
    ]


def init():
    try:
        cfg.CONF([], project='nectar-osc',
            default_config_files=['~/.nectar-osc.conf'])
    except cfg.ConfigFilesNotFoundError:
        print('generating config file ~/.nectar-osc.conf')
        conf = cfg.ConfigOpts()
        generator.register_cli_opts(conf)
        conf.namespace = ['nectar_osc']
        with open(homedir + '/' + '.nectar-osc.conf', 'w') as conf_file:
            generator.generate(conf, conf_file)
