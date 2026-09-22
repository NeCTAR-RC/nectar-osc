# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import Mock

from nectar_osc import network
from nectar_osc.tests import test


def _rule(**kwargs):
    """A neutron security group rule dict with the given overrides"""
    rule = {
        'direction': 'ingress',
        'ethertype': 'IPv4',
        'protocol': None,
        'port_range_min': None,
        'port_range_max': None,
        'remote_ip_prefix': None,
        'remote_group_id': None,
    }
    rule.update(kwargs)
    return rule


SSH_RULE = _rule(
    protocol='tcp',
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix='0.0.0.0/0',
)
WEB_RULE = _rule(
    protocol='tcp',
    port_range_min=80,
    port_range_max=443,
    remote_group_id='sg-web',
)
EGRESS_RULE = _rule(direction='egress', ethertype='IPv6')

SECGROUPS = [
    {
        'id': 'sg-1',
        'name': 'default',
        'security_group_rules': [WEB_RULE, SSH_RULE, EGRESS_RULE],
    },
    {'id': 'sg-2', 'name': 'empty', 'security_group_rules': []},
]


class TestGetSgRemote(test.TestCase):
    def test_cidr(self):
        self.assertEqual(
            '10.0.0.0/8 (CIDR)',
            network._get_sg_remote(_rule(remote_ip_prefix='10.0.0.0/8')),
        )

    def test_group(self):
        self.assertEqual(
            'sg-web (group)',
            network._get_sg_remote(_rule(remote_group_id='sg-web')),
        )

    def test_cidr_takes_precedence(self):
        self.assertEqual(
            '10.0.0.0/8 (CIDR)',
            network._get_sg_remote(
                _rule(remote_ip_prefix='10.0.0.0/8', remote_group_id='sg')
            ),
        )

    def test_none(self):
        self.assertIsNone(network._get_sg_remote(_rule()))


class TestGetSgProtocolPort(test.TestCase):
    def test_tcp_single_port(self):
        self.assertEqual(
            '22/tcp',
            network._get_sg_protocol_port(
                _rule(protocol='tcp', port_range_min=22, port_range_max=22)
            ),
        )

    def test_udp_port_range(self):
        self.assertEqual(
            '5000-5100/udp',
            network._get_sg_protocol_port(
                _rule(protocol='udp', port_range_min=5000, port_range_max=5100)
            ),
        )

    def test_tcp_all_ports(self):
        self.assertEqual(
            'tcp', network._get_sg_protocol_port(_rule(protocol='tcp'))
        )

    def test_icmp_type_and_code(self):
        self.assertEqual(
            'icmp (type:8, code:0)',
            network._get_sg_protocol_port(
                _rule(protocol='icmp', port_range_min=8, port_range_max=0)
            ),
        )

    def test_icmp_type_only(self):
        self.assertEqual(
            'icmp (type:8)',
            network._get_sg_protocol_port(
                _rule(protocol='icmp', port_range_min=8)
            ),
        )

    def test_icmp_code_only(self):
        self.assertEqual(
            'icmp (code:3)',
            network._get_sg_protocol_port(
                _rule(protocol='icmp', port_range_max=3)
            ),
        )

    def test_icmp_any(self):
        self.assertEqual(
            'icmp', network._get_sg_protocol_port(_rule(protocol='icmp'))
        )

    def test_other_protocol_ignores_ports(self):
        self.assertEqual(
            'gre',
            network._get_sg_protocol_port(
                _rule(protocol='gre', port_range_min=1, port_range_max=2)
            ),
        )

    def test_any_protocol(self):
        self.assertIsNone(network._get_sg_protocol_port(_rule()))


class TestFormatSgRule(test.TestCase):
    def test_full_rule(self):
        self.assertEqual(
            'ingress, IPv4, 22/tcp, remote_ip_prefix: 0.0.0.0/0',
            network._format_sg_rule(SSH_RULE),
        )

    def test_remote_group(self):
        self.assertEqual(
            'ingress, IPv4, 80-443/tcp, remote_group_id: sg-web',
            network._format_sg_rule(WEB_RULE),
        )

    def test_minimal_rule(self):
        """Empty fields are left out"""
        self.assertEqual('egress, IPv6', network._format_sg_rule(EGRESS_RULE))


class TestFormatSgRules(test.TestCase):
    def test_sorted_one_per_line(self):
        self.assertEqual(
            'egress, IPv6\n'
            'ingress, IPv4, 22/tcp, remote_ip_prefix: 0.0.0.0/0\n'
            'ingress, IPv4, 80-443/tcp, remote_group_id: sg-web',
            network._format_sg_rules(SECGROUPS[0]),
        )

    def test_no_rules(self):
        self.assertEqual('', network._format_sg_rules(SECGROUPS[1]))

    def test_bad_data(self):
        """Any problem formatting the rules gives an empty string"""
        self.assertEqual('', network._format_sg_rules({}))
        self.assertEqual(
            '',
            network._format_sg_rules({'security_group_rules': [{}]}),
        )
        self.assertEqual(
            '', network._format_sg_rules({'security_group_rules': None})
        )


class TestFormatSecgroups(test.TestCase):
    def test_text(self):
        output = network._format_secgroups(SECGROUPS)
        lines = output.splitlines()
        self.assertEqual('Security Groups:', lines[0])
        self.assertIn('| ID   | Name    | Rules', lines[2])
        # A multiline rule cell spans several table rows
        self.assertIn('| sg-1 | default | egress, IPv6', output)
        self.assertIn('|      |         | ingress, IPv4, 22/tcp', output)
        self.assertIn('| sg-2 | empty   |', output)
        self.assertNotIn('<table', output)

    def test_html(self):
        output = network._format_secgroups(SECGROUPS, style='html')
        self.assertTrue(output.startswith('<b>Security Groups</b>'))
        self.assertIn(
            '<table border="1" '
            'style="border-width: 1px; border-collapse: collapse;">',
            output,
        )
        for heading in ['ID', 'Name', 'Rules']:
            self.assertIn(f'<th>{heading}</th>', output)
        for cell in ['sg-1', 'default', 'sg-2', 'empty']:
            self.assertIn(f'<td>{cell}</td>', output)
        self.assertIn('remote_ip_prefix: 0.0.0.0/0', output)

    def test_empty(self):
        output = network._format_secgroups([])
        self.assertEqual('Security Groups:', output.splitlines()[0])
        self.assertNotIn('sg-', output)


class TestShowInstanceSecurityGroups(test.TestCase):
    def _clients(self, ports, security_groups=SECGROUPS):
        clients = Mock()
        clients.network.ports.return_value = ports
        clients.network.security_groups.return_value = security_groups
        return clients

    def test_show(self):
        clients = self._clients(
            [
                {'security_groups': ['sg-1', 'sg-2']},
                {'security_groups': ['sg-3']},
            ]
        )
        output = network.show_instance_security_groups(clients, 'inst-1')
        clients.network.ports.assert_called_once_with(device_id='inst-1')
        clients.network.security_groups.assert_called_once_with(
            id=['sg-1', 'sg-2', 'sg-3']
        )
        self.assertEqual(network._format_secgroups(SECGROUPS), output)

    def test_show_html(self):
        clients = self._clients([{'security_groups': ['sg-1']}])
        output = network.show_instance_security_groups(
            clients, 'inst-1', style='html'
        )
        self.assertEqual(
            network._format_secgroups(SECGROUPS, style='html'), output
        )

    def test_no_ports(self):
        clients = self._clients([])
        self.assertIsNone(
            network.show_instance_security_groups(clients, 'inst-1')
        )
        clients.network.security_groups.assert_not_called()

    def test_ports_without_security_groups(self):
        clients = self._clients([{'security_groups': []}])
        self.assertIsNone(
            network.show_instance_security_groups(clients, 'inst-1')
        )
        clients.network.security_groups.assert_not_called()
