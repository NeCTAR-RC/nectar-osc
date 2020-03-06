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

from oslo_config import cfg


freshdesk_opts = [
    cfg.StrOpt('api_key', required=True),
    cfg.IntOpt('email_config_id', required=True),
    cfg.IntOpt('group_id', required=True),
    cfg.StrOpt('domain', required=True),
]


cfg.CONF.register_opts(freshdesk_opts, group='freshdesk')


def init():
    cfg.CONF([], project='nectar-osc',
         default_config_files=['~/.nectar-osc.conf'])
