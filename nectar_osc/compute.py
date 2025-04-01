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

import json

from openstackclient.compute.v2 import server as osc_server
from prettytable import PrettyTable


def _format_instance(d, style=None):
    """Pretty print instance info for the command line"""
    pt = PrettyTable(['Property', 'Value'], caching=False)
    pt.align = 'l'
    for k, v in sorted(d.items()):
        # convert dict to str to check length
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        # if value has a newline, add in multiple rows
        # e.g. fault with stacktrace
        if v and isinstance(v, str) and (r'\n' in v or '\r' in v):
            # '\r' would break the table, so remove it.
            if '\r' in v:
                v = v.replace('\r', '')
            lines = v.strip().split(r'\n')
            col1 = k
            for line in lines:
                pt.add_row([col1, line])
                col1 = ''
        else:
            if v is None:
                v = '-'
            pt.add_row([k, v])

    if style == 'html':
        output = '<b>Instance details</b>'
        output += pt.get_html_string(
            attributes={
                'border': '1',
                'style': 'border-width: 1px; border-collapse: collapse;',
            }
        )
    else:
        output = 'Instance details:\n'
        output += pt.get_string()
    return output


def show_instance(clients, instance_id, style=None):
    instance = clients.compute.get_server(instance_id)
    data = osc_server._prep_server_detail(
        clients.compute, clients.image, instance, refresh=False
    )

    return _format_instance(data, style=style)
