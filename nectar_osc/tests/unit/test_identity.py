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

from keystoneauth1.exceptions.http import NotFound

from nectar_osc import identity
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


class TestIdentity(test.TestCase):
    def test_get_user(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_user(clients.identity, 'jim.spriggs@gmail.com')
        self.assertIsNotNone(
            identity.get_user(clients.identity, 'fred.nurke@gmail.com')
        )

    def test_get_project(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_project(clients.identity, 'route66')
        self.assertIsNotNone(identity.get_project(clients.identity, 'area54'))

    def test_get_roles(self):
        clients = fakes.make_fake_clients()
        self.assertIsNotNone(identity.get_role(clients.identity, 'Member'))
        self.assertIsNotNone(
            identity.get_role(clients.identity, 'TenantManager')
        )

    def test_get_user_emails_with_roles(self):
        clients = fakes.make_fake_clients()
        emails = identity.get_user_emails_with_roles(
            clients.identity,
            project_id='44444444-1111-1111-1111-111111111111',
            role_names=['Member', 'TenantManager'],
        )
        self.assertEqual(
            ['terry.towling@gmail.com', 'fred.nurke@gmail.com'], emails
        )

    def test_get_user_emails_by_role(self):
        clients = fakes.make_fake_clients()
        emails = identity.get_user_emails_by_role(
            clients.identity,
            project_id='44444444-1111-1111-1111-111111111111',
            role_names=['Member', 'TenantManager'],
        )
        self.assertEqual(
            {
                'Member': [
                    'terry.towling@gmail.com',
                    'fred.nurke@gmail.com',
                ],
                'TenantManager': ['fred.nurke@gmail.com'],
            },
            emails,
        )

    def test_get_user_emails_by_role_case_insensitive(self):
        """Production role names may not match the case of the
        requested names (e.g. 'tenantmanager' vs 'TenantManager').
        Keystone resolves role names case-insensitively and the
        role matching must honour that.
        """
        roles = [
            fakes.FakeRole(id=fakes.ROLES[0].id, name='member'),
            fakes.FakeRole(id=fakes.ROLES[1].id, name='tenantmanager'),
        ]
        clients = fakes.make_fake_clients(roles=roles)
        emails = identity.get_user_emails_by_role(
            clients.identity,
            project_id='44444444-1111-1111-1111-111111111111',
            role_names=['Member', 'TenantManager'],
        )
        self.assertEqual(
            {
                'Member': [
                    'terry.towling@gmail.com',
                    'fred.nurke@gmail.com',
                ],
                'TenantManager': ['fred.nurke@gmail.com'],
            },
            emails,
        )
