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

from prettytable import PrettyTable

from neutronclient.v2_0 import client as nclient


def _get_sg_remote(rule):
    if rule['remote_ip_prefix']:
        remote = '%s (CIDR)' % rule['remote_ip_prefix']
    elif rule['remote_group_id']:
        remote = '%s (group)' % rule['remote_group_id']
    else:
        remote = None
    return remote


def _get_sg_protocol_port(rule):
    proto = rule['protocol']
    port_min = rule['port_range_min']
    port_max = rule['port_range_max']
    if proto in ('tcp', 'udp'):
        if (port_min and port_min == port_max):
            protocol_port = '%s/%s' % (port_min, proto)
        elif port_min:
            protocol_port = '%s-%s/%s' % (port_min, port_max, proto)
        else:
            protocol_port = proto
    elif proto == 'icmp':
        icmp_opts = []
        if port_min is not None:
            icmp_opts.append('type:%s' % port_min)
        if port_max is not None:
            icmp_opts.append('code:%s' % port_max)

        if icmp_opts:
            protocol_port = 'icmp (%s)' % ', '.join(icmp_opts)
        else:
            protocol_port = 'icmp'
    elif proto is not None:
        # port_range_min/max are not recognized for protocol
        # other than TCP, UDP and ICMP.
        protocol_port = proto
    else:
        protocol_port = None
    return protocol_port


def _format_sg_rule(rule):
    formatted = []
    for field in ['direction',
                  'ethertype',
                  ('protocol_port', _get_sg_protocol_port),
                  'remote_ip_prefix',
                  'remote_group_id']:
        if isinstance(field, tuple):
            field, get_method = field
            data = get_method(rule)
        else:
            data = rule[field]
        if not data:
            continue
        if field in ('remote_ip_prefix', 'remote_group_id'):
            data = '%s: %s' % (field, data)
        formatted.append(data)
    return ', '.join(formatted)


def _format_sg_rules(secgroup):
    try:
        return '\n'.join(sorted([_format_sg_rule(rule) for rule
                                 in secgroup['security_group_rules']]))
    except Exception:
        return ''


def _format_secgroups(security_groups, style=None):
    pt = PrettyTable(['ID', 'Name', 'Rules'], caching=False)
    pt.align = 'l'

    for sg in security_groups['security_groups']:
        pt.add_row([sg['id'], sg['name'],
                    _format_sg_rules(sg)])

    if style == 'html':
        output = '<b>Security Groups</b>'
        output += pt.get_html_string(attributes={
            'border': 1,
            'style': 'border-width: 1px; border-collapse: collapse;'
        })
    else:
        output = 'Security Groups:\n'
        output += pt.get_string()
    return output


def show_instance_security_groups(clients, instance_id, style=None):

    nc = nclient.Client(session=clients.session)

    ports = nc.list_ports(device_id=instance_id)
    sg_ids = [sg for sgs in [p['security_groups']
              for p in ports['ports']] for sg in sgs]
    security_groups = nc.list_security_groups(id=sg_ids)

    return _format_secgroups(security_groups, style=style)
