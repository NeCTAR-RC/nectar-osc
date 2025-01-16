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

import unittest

from nectar_osc import compute
from nectar_osc.tests.unit import fakes


class TestCompute(unittest.TestCase):
    def test_extract_server_info(self):
        clients = fakes.make_fake_clients()
        server = clients.compute.servers.get(
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
        self.assertEqual('cn1.twilight.nectar.org.au', info['host'])
        self.assertEqual('33333333-1111-1111-1111-111111111111', info['user'])
        self.assertEqual(
            '44444444-1111-1111-1111-111111111111', info['project']
        )
        self.assertEqual('fred.nurke@gmail.com', info['email'])
        self.assertEqual('Fred Nurke', info['fullname'])
        self.assertEqual(['192.168.76.119'], info['addresses'])
        self.assertEqual('area54', info['project_name'])
        self.assertEqual('twilight', info['zone'])

    def test_all_instances(self):
        clients = fakes.make_fake_clients()
        all = compute.all_instances(clients)
        self.assertEqual(len(fakes.SERVERS), len(all))
        self.assertEqual(
            1, len(compute.all_instances(clients, status='STOPPED'))
        )
        self.assertEqual(
            1, len(compute.all_instances(clients, zones=['twilight']))
        )
        self.assertEqual(
            3,
            len(compute.all_instances(clients, zones=['twilight', 'danger'])),
        )
        self.assertEqual(
            1,
            len(
                compute.all_instances(
                    clients, hosts=['cn1.twilight.nectar.org.au']
                )
            ),
        )
        self.assertEqual(
            2,
            len(
                compute.all_instances(
                    clients,
                    hosts=[
                        'cn1.twilight.nectar.org.au',
                        'cn1.danger.nectar.org.au',
                    ],
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
