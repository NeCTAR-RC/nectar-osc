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

import os
import sys

from oslo_config import cfg
from oslo_config import generator


freshdesk_opts = [
    cfg.StrOpt('api_key', help='your freshdesk api key'),
    cfg.IntOpt(
        'email_config_id',
        default='6000071619',
        help='freshdesk email config id',
    ),
    cfg.IntOpt('group_id', default='6000208874', help='freshdesk group id'),
    cfg.StrOpt(
        'domain', default='dhdnectar.freshdesk.com', help='freshdesk domain'
    ),
]

mailout_opts = [
    cfg.StrOpt(
        'work_dir',
        default='~/.cache/os-mailout/freshdesk/',
        help='default working directory; i.e. where mailout dirs are created',
    ),
]

nova_opts = [
    cfg.IntOpt(
        'page_size',
        default='-1',
        help='nova result page size when listing instances',
    ),
]


cfg.CONF.register_opts(freshdesk_opts, group='freshdesk')
cfg.CONF.register_opts(mailout_opts, group='mailout')
cfg.CONF.register_opts(nova_opts, group='nova')


def list_opts():
    return [
        ('freshdesk', freshdesk_opts),
        ('mailout', mailout_opts),
        ('nova', nova_opts),
    ]


def init(pathname='~/.nectar-osc.conf'):
    real_pathname = os.path.expanduser(pathname)
    try:
        cfg.CONF(
            [],
            project='nectar-osc',
            default_config_files=[real_pathname],
        )
    except cfg.ConfigFilesNotFoundError:
        print(f'generating config file {real_pathname}')
        dirname = os.path.dirname(real_pathname)
        if not os.path.isdir(dirname):
            print(f"config directory {dirname} doesn't exist")
            sys.exit(1)
        conf = cfg.ConfigOpts()
        generator.register_cli_opts(conf)
        conf.namespace = ['nectar_osc']
        with open(real_pathname, 'w') as conf_file:
            generator.generate(conf, conf_file)
