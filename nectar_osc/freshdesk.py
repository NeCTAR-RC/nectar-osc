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

try:
    from freshdesk.v2 import api
except ImportError:
    api = None

from nectar_osc import config
from oslo_config import cfg


CONF = cfg.CONF


def get_client():
    if not api:
        print("To use this tool, you will need to also install the"
              "python-freshdesk package: \n"
              "  $ pip install python-freshdesk")
        sys.exit(1)

    msg = '\n'.join([
        'No Freshdesk api key found in your config file.',
        '',
        'To find your Freshdesk API key by following the guide here:',
        'https://support.freshdesk.com/support/solutions/'
        'articles/215517-how-to-find-your-api-key',
        '',
        'Then add the following config to your configuration',
        'file (~/.nectar-osc.conf):',
        '',
        '  [freshdesk]',
        '  api_key = <your api key>',
    ])

    config.init()

    if not CONF.freshdesk.api_key:
        print(msg)
        sys.exit(1)

    return api.API(CONF.freshdesk.domain, CONF.freshdesk.api_key)
