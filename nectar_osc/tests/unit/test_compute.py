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

import json
from unittest.mock import Mock
from unittest.mock import patch

from oslo_config import cfg

from nectar_osc import compute
from nectar_osc import identity
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


CONF = cfg.CONF

FRED = '33333333-1111-1111-1111-111111111111'
TROVE_USER = '33333333-1111-1111-1111-111111111114'
AREA54 = '44444444-1111-1111-1111-111111111111'
SANANDREAS = '44444444-1111-1111-1111-111111111112'


def make_server(**kwargs):
    """A server in project area54 launched by fred, with overrides"""
    params = dict(
        id='00000000-1111-1111-1111-111111111119',
        name='nine',
        status='ACTIVE',
        flavor={'id': '11111111-1111-1111-1111-111111111111', 'name': 'lemon'},
        compute_host='cn9.danger.nectar.org.au',
        zone='danger',
        image={'id': '22222222-1111-1111-1111-111111111119'},
        metadata={},
        addresses={'net_name': [{'addr': '192.168.76.9'}]},
        user_id=FRED,
        project_id=AREA54,
    )
    params.update(kwargs)
    return fakes.FakeServer(**params)


def table_rows(output):
    """The (property, value) rows of a text formatted PrettyTable"""
    rows = []
    for line in output.splitlines():
        if not line.startswith('| '):
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if cells != ['Property', 'Value']:
            rows.append(tuple(cells))
    return rows


class TestFormatInstance(test.TestCase):
    def test_text(self):
        output = compute._format_instance(
            {'name': 'one', 'id': 'abc', 'status': 'ACTIVE'}
        )
        self.assertEqual('Instance details:', output.splitlines()[0])
        self.assertNotIn('<table', output)
        # Rows are sorted by property name
        self.assertEqual(
            [('id', 'abc'), ('name', 'one'), ('status', 'ACTIVE')],
            table_rows(output),
        )

    def test_none_and_empty_values(self):
        output = compute._format_instance({'a': None, 'b': '', 'c': 0})
        self.assertEqual(
            [('a', '-'), ('b', ''), ('c', '0')], table_rows(output)
        )

    def test_dict_and_list_values(self):
        addresses = {'net': [{'addr': '10.0.0.1'}]}
        tags = ['x', 'y']
        output = compute._format_instance(
            {'addresses': addresses, 'tags': tags, 'empty': {}}
        )
        self.assertEqual(
            [
                ('addresses', json.dumps(addresses)),
                ('empty', '{}'),
                ('tags', json.dumps(tags)),
            ],
            table_rows(output),
        )

    def test_multiline_value(self):
        """A value with (escaped) newlines is spread over several rows,
        e.g. a fault with a stacktrace.
        """
        output = compute._format_instance(
            {'fault': r'Traceback\n  File "x.py"\nError: boom', 'id': 'abc'}
        )
        self.assertEqual(
            [
                ('fault', 'Traceback'),
                ('', 'File "x.py"'),
                ('', 'Error: boom'),
                ('id', 'abc'),
            ],
            table_rows(output),
        )

    def test_carriage_returns_removed(self):
        output = compute._format_instance(
            {'a': 'one\rtwo', 'b': 'three\r' + r'\n' + 'four'}
        )
        self.assertEqual(
            [('a', 'onetwo'), ('b', 'three'), ('', 'four')],
            table_rows(output),
        )
        self.assertNotIn('\r', output)

    def test_html(self):
        output = compute._format_instance(
            {'name': 'one', 'id': 'abc', 'fault': None}, style='html'
        )
        self.assertTrue(output.startswith('<b>Instance details</b>'))
        self.assertIn(
            '<table border="1" '
            'style="border-width: 1px; border-collapse: collapse;">',
            output,
        )
        self.assertIn('<th>Property</th>', output)
        self.assertIn('<th>Value</th>', output)
        for cell in ['abc', 'one', 'fault', '-']:
            self.assertIn(f'<td>{cell}</td>', output)
        self.assertNotIn('Instance details:', output)


class TestShowInstance(test.TestCase):
    @patch('nectar_osc.compute.osc_server._prep_server_detail')
    def test_show_instance(self, mock_prep):
        clients = Mock()
        mock_prep.return_value = {'id': 'abc', 'name': 'one'}
        output = compute.show_instance(clients, 'abc')
        clients.compute.get_server.assert_called_once_with('abc')
        mock_prep.assert_called_once_with(
            clients.compute,
            clients.image,
            clients.compute.get_server.return_value,
            refresh=False,
        )
        self.assertEqual(
            compute._format_instance({'id': 'abc', 'name': 'one'}), output
        )

    @patch('nectar_osc.compute.osc_server._prep_server_detail')
    def test_show_instance_html(self, mock_prep):
        clients = Mock()
        mock_prep.return_value = {'id': 'abc', 'name': 'one'}
        output = compute.show_instance(clients, 'abc', style='html')
        self.assertEqual(
            compute._format_instance(
                {'id': 'abc', 'name': 'one'}, style='html'
            ),
            output,
        )


class TestExtractServerInfo(test.TestCase):
    def test_extract_server_info(self):
        clients = fakes.make_fake_clients()
        server = clients.compute.servers.get_server(
            '00000000-1111-1111-1111-111111111111'
        )
        info = compute.extract_server_info(clients, server)
        self.assertIsNotNone(info)
        self.assertEqual('00000000-1111-1111-1111-111111111111', info['id'])
        self.assertEqual('one', info['name'])
        self.assertEqual('STOPPED', info['status'])
        self.assertEqual(
            '11111111-1111-1111-1111-111111111111', info['flavor']
        )
        self.assertEqual('22222222-1111-1111-1111-111111111111', info['image'])
        self.assertEqual('cn1', info['host'])
        self.assertEqual('cn1.twilight.nectar.org.au', info['full_host'])
        self.assertEqual('33333333-1111-1111-1111-111111111111', info['user'])
        self.assertEqual(
            '44444444-1111-1111-1111-111111111111', info['project']
        )
        self.assertEqual('fred.nurke@gmail.com', info['email'])
        self.assertEqual('Fred Nurke', info['fullname'])
        self.assertEqual(['192.168.76.119'], info['addresses'])
        self.assertEqual('area54', info['project_name'])
        self.assertEqual('twilight', info['zone'])

    def test_populates_caches(self):
        clients = fakes.make_fake_clients()
        info = compute.extract_server_info(clients, make_server())
        self.assertIn(info['user'], identity.user_cache)
        self.assertIn(info['project'], identity.project_cache)
        # A second server from the same owner is served from the cache
        mock_identity = Mock()
        clients.identity = mock_identity
        info = compute.extract_server_info(clients, make_server(id='x'))
        self.assertEqual('area54', info['project_name'])
        self.assertEqual('fred.nurke@gmail.com', info['email'])
        mock_identity.users.get.assert_not_called()
        mock_identity.projects.get.assert_not_called()

    def test_metadata_overrides_owner(self):
        """Tier 2 services record the real owner in the metadata"""
        clients = fakes.make_fake_clients()
        server = make_server(
            user_id=TROVE_USER,
            project_id='44444444-1111-1111-1111-111111111113',
            metadata={
                'user_id': '33333333-1111-1111-1111-111111111113',
                'project_id': SANANDREAS,
            },
        )
        info = compute.extract_server_info(clients, server)
        self.assertEqual('33333333-1111-1111-1111-111111111113', info['user'])
        self.assertEqual(SANANDREAS, info['project'])
        self.assertEqual('sanandreas', info['project_name'])
        self.assertEqual('randy.katz@gmail.com', info['email'])
        self.assertEqual('Randolph Katz', info['fullname'])

    def test_partial_metadata_ignored(self):
        """Both user_id and project_id are needed in the metadata"""
        clients = fakes.make_fake_clients()
        for metadata in [
            {},
            None,
            {'user_id': '33333333-1111-1111-1111-111111111113'},
            {'project_id': SANANDREAS},
            {'other': 'stuff'},
        ]:
            server = make_server(metadata=metadata)
            info = compute.extract_server_info(clients, server)
            self.assertEqual(FRED, info['user'], metadata)
            self.assertEqual(AREA54, info['project'], metadata)
            self.assertEqual('area54', info['project_name'], metadata)

    def test_not_booted_from_image(self):
        clients = fakes.make_fake_clients()
        for image in [None, {}, '', {'name': 'no-id'}]:
            server = make_server(image=image)
            info = compute.extract_server_info(clients, server)
            self.assertIsNone(info['image'], image)

    def test_disabled_user(self):
        """Disabled users are not notified"""
        users = [
            fakes.FakeUser(
                id=FRED,
                name='fred.nurke@gmail.com',
                email='fred.nurke@gmail.com',
                full_name='Fred Nurke',
                enabled=False,
            )
        ]
        clients = fakes.make_fake_clients(users=users)
        info = compute.extract_server_info(clients, make_server())
        self.assertEqual(FRED, info['user'])
        self.assertIsNone(info['email'])
        self.assertIsNone(info['fullname'])

    def test_user_without_email(self):
        """Service users have no email; their name is used instead"""
        clients = fakes.make_fake_clients()
        info = compute.extract_server_info(
            clients, make_server(user_id=TROVE_USER)
        )
        self.assertEqual('trove', info['email'])
        self.assertIsNone(info['fullname'])

    def test_user_without_full_name(self):
        users = [
            fakes.FakeUser(
                id=FRED,
                name='fred.nurke@gmail.com',
                email='fred.nurke@gmail.com',
                full_name=None,
            )
        ]
        del users[0].full_name
        clients = fakes.make_fake_clients(users=users)
        info = compute.extract_server_info(clients, make_server())
        self.assertEqual('fred.nurke@gmail.com', info['email'])
        self.assertIsNone(info['fullname'])

    def test_addresses(self):
        clients = fakes.make_fake_clients()
        server = make_server(
            addresses={
                'private': [
                    {'addr': '10.0.0.1'},
                    {'addr': ''},
                    {'addr': None},
                ],
                'public': [{'addr': '203.0.113.1'}, {'addr': '10.0.0.1'}],
                'empty': [],
            }
        )
        info = compute.extract_server_info(clients, server)
        self.assertEqual(
            ['10.0.0.1', '203.0.113.1'], sorted(info['addresses'])
        )

    def test_missing_attribute(self):
        clients = fakes.make_fake_clients()
        server = make_server()
        del server.ext['OS-EXT-AZ:availability_zone']
        with self.assertRaisesRegex(
            KeyError, 'OS-EXT-AZ:availability_zone missing in context'
        ):
            compute.extract_server_info(clients, server)

    def test_extract_ip(self):
        self.assertEqual([], compute._extract_ip(make_server(addresses={})))
        self.assertEqual(['192.168.76.9'], compute._extract_ip(make_server()))


class TestInstanceExtractor(test.TestCase):
    def _set_page_size(self, page_size):
        CONF.set_override('page_size', page_size, group='nova')
        self.addCleanup(CONF.clear_override, 'page_size', group='nova')

    def test_get_opts_defaults(self):
        extractor = compute.InstanceExtractor(fakes.make_fake_clients())
        self.assertEqual({'all_projects': True}, extractor.get_opts())

    def test_get_opts_status_all(self):
        extractor = compute.InstanceExtractor(
            fakes.make_fake_clients(), status='ALL'
        )
        self.assertEqual({'all_projects': True}, extractor.get_opts())

    def test_get_opts(self):
        extractor = compute.InstanceExtractor(
            fakes.make_fake_clients(),
            status='ACTIVE',
            image_id='img',
            user_id='usr',
            project_id='prj',
            zones=['z'],
            hosts=['h'],
            ips=['1.2.3.4'],
            limit=3,
        )
        # zones, hosts, ips and limit are handled client side
        self.assertEqual(
            {
                'all_projects': True,
                'status': 'ACTIVE',
                'image': 'img',
                'user_id': 'usr',
                'project_id': 'prj',
            },
            extractor.get_opts(),
        )

    def test_get_opts_page_size(self):
        self._set_page_size(100)
        extractor = compute.InstanceExtractor(fakes.make_fake_clients())
        self.assertEqual(
            {'all_projects': True, 'limit': 100}, extractor.get_opts()
        )
        self._set_page_size(0)
        self.assertEqual({'all_projects': True}, extractor.get_opts())

    def test_all_instances_paged(self):
        """With a nova page size, the extractor pages through nova's
        results using markers.
        """
        self._set_page_size(1)
        clients = fakes.make_fake_clients()
        clients.compute.servers = Mock(wraps=clients.compute.servers)
        all = compute.all_instances(clients)
        self.assertEqual(len(fakes.SERVERS), len(all))
        self.assertEqual(
            [s.id for s in fakes.SERVERS], [info['id'] for info in all]
        )
        # 4 pages of one server, then an empty page
        self.assertEqual(5, clients.compute.servers.call_count)
        markers = [
            call.kwargs.get('marker')
            for call in clients.compute.servers.call_args_list
        ]
        self.assertEqual([None] + [s.id for s in fakes.SERVERS], markers)

    def test_all_instances_repeated_marker(self):
        """Nova can keep returning the marker instance (e.g. one stuck
        in BUILD); that must not loop forever.
        """
        clients = fakes.make_fake_clients()
        clients.compute.servers = Mock(return_value=[fakes.SERVERS[0]])
        all = compute.all_instances(clients)
        self.assertEqual(1, len(all))
        self.assertEqual(fakes.SERVERS[0].id, all[0]['id'])
        self.assertEqual(2, clients.compute.servers.call_count)

    def test_all_instances_hosts_take_precedence(self):
        """Hosts are queried, zones are then filtered client side"""
        clients = fakes.make_fake_clients()
        all = compute.all_instances(clients, hosts=['cn1'], zones=['twilight'])
        self.assertEqual(['one'], [info['name'] for info in all])
        all = compute.all_instances(clients, hosts=['cn1'], zones=['danger'])
        self.assertEqual(['two'], [info['name'] for info in all])

    def test_all_instances_zone_and_ip(self):
        clients = fakes.make_fake_clients()
        all = compute.all_instances(
            clients, zones=['danger'], ips=['192.168.76.123']
        )
        self.assertEqual(['three', 'database'], [info['name'] for info in all])

    def test_all_instances_project_and_user(self):
        clients = fakes.make_fake_clients()
        all = compute.all_instances(
            clients,
            project_id=SANANDREAS,
            user_id='33333333-1111-1111-1111-111111111113',
        )
        # 'database' is a trove instance in the trove project but its
        # metadata records the sanandreas project and randy
        self.assertEqual(['database', 'three'], [info['name'] for info in all])

    def test_all_instances_limit(self):
        clients = fakes.make_fake_clients()
        all = compute.all_instances(clients, limit=2)
        self.assertEqual(['one', 'two'], [info['name'] for info in all])
        all = compute.all_instances(clients, limit=10)
        self.assertEqual(len(fakes.SERVERS), len(all))

    def test_match_az(self):
        server = fakes.SERVERS[0]  # twilight
        clients = fakes.make_fake_clients()
        self.assertTrue(compute.InstanceExtractor(clients)._match_az(server))
        self.assertTrue(
            compute.InstanceExtractor(
                clients, zones=['danger', 'twilight']
            )._match_az(server)
        )
        self.assertFalse(
            compute.InstanceExtractor(clients, zones=['danger'])._match_az(
                server
            )
        )

    def test_match_ip_address(self):
        server = make_server(
            addresses={
                'a': [{'addr': '10.0.0.1'}],
                'b': [{'addr': '203.0.113.1'}, {'addr': '203.0.113.2'}],
            }
        )
        clients = fakes.make_fake_clients()

        def match(ips):
            return compute.InstanceExtractor(
                clients, ips=ips
            )._match_ip_address(server)

        self.assertTrue(match(None))
        self.assertTrue(match([]))
        self.assertTrue(match(['10.0.0.1']))
        self.assertTrue(match(['203.0.113.2']))
        self.assertTrue(match(['1.1.1.1', '203.0.113.1']))
        self.assertFalse(match(['1.1.1.1']))
        # Substring match
        self.assertTrue(match(['203.0.113']))

    def test_match_proj_user(self):
        server = make_server(
            metadata={'project_id': 'p1', 'user_id': 'u1'},
        )
        clients = fakes.make_fake_clients()

        def match(**kwargs):
            return compute.InstanceExtractor(
                clients, **kwargs
            )._match_proj_user(server)

        self.assertTrue(match())
        self.assertTrue(match(project_id='p1'))
        self.assertTrue(match(user_id='u1'))
        self.assertTrue(match(project_id='p1', user_id='u1'))
        self.assertFalse(match(project_id='p2'))
        self.assertFalse(match(user_id='u2'))
        self.assertFalse(match(project_id='p1', user_id='u2'))
        self.assertFalse(match(project_id='p2', user_id='u1'))

    def test_match_proj_user_without_metadata(self):
        server = make_server(metadata={})
        clients = fakes.make_fake_clients()
        extractor = compute.InstanceExtractor(clients, project_id='p1')
        self.assertFalse(extractor._match_proj_user(server))


class TestCompute(test.TestCase):
    def test_all_instances(self):
        clients = fakes.make_fake_clients()
        all = compute.all_instances(clients)
        self.assertEqual(len(fakes.SERVERS), len(all))
        self.assertEqual(
            1, len(compute.all_instances(clients, status='STOPPED'))
        )
        self.assertEqual(
            2,
            len(
                compute.all_instances(
                    clients, image_id='22222222-1111-1111-1111-111111111112'
                )
            ),
        )
        self.assertEqual(
            1, len(compute.all_instances(clients, zones=['twilight']))
        )
        self.assertEqual(
            4,
            len(compute.all_instances(clients, zones=['twilight', 'danger'])),
        )
        self.assertEqual(
            0,
            len(compute.all_instances(clients, zones=['end'])),
        )
        self.assertEqual(
            2,
            len(compute.all_instances(clients, hosts=['cn1'])),
        )
        self.assertEqual(
            2,
            len(
                compute.all_instances(
                    clients,
                    user_id='33333333-1111-1111-1111-111111111111',
                )
            ),
        )
        self.assertEqual(
            2,
            len(
                compute.all_instances(
                    clients,
                    user_id='33333333-1111-1111-1111-111111111113',
                )
            ),
        )
        self.assertEqual(
            2,
            len(
                compute.all_instances(
                    clients,
                    project_id='44444444-1111-1111-1111-111111111112',
                )
            ),
        )
        self.assertEqual(
            0,
            len(
                compute.all_instances(
                    clients,
                    project_id='44444444-1111-1111-1111-111111111199',
                )
            ),
        )
        self.assertEqual(
            1,
            len(
                compute.all_instances(
                    clients,
                    ips=[
                        '192.168.76.112',
                    ],
                )
            ),
        )
        self.assertEqual(
            3,
            len(
                compute.all_instances(
                    clients,
                    hosts=['cn1', 'cn2'],
                )
            ),
        )
        self.assertEqual(
            1,
            len(
                compute.all_instances(
                    clients,
                    hosts=['cn1', 'cn2'],
                    limit=1,
                )
            ),
        )

    def test_all_instances_throttled(self):
        """Test all_instances with a (simulated) limit on the
        number of servers returned by the Nova list request.
        This exercises the marker handling.
        """

        clients = fakes.make_fake_clients(max_response=1)
        all = compute.all_instances(clients)
        self.assertEqual(len(fakes.SERVERS), len(all))
