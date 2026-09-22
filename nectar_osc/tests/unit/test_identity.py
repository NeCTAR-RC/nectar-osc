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

from keystoneauth1.exceptions.http import NotFound

from nectar_osc import identity
from nectar_osc.tests import test
from nectar_osc.tests.unit import fakes


FRED = '33333333-1111-1111-1111-111111111111'
TERRY = '33333333-1111-1111-1111-111111111112'
RANDY = '33333333-1111-1111-1111-111111111113'
TROVE_USER = '33333333-1111-1111-1111-111111111114'
AREA54 = '44444444-1111-1111-1111-111111111111'
SANANDREAS = '44444444-1111-1111-1111-111111111112'
TROVE = '44444444-1111-1111-1111-111111111113'
MEMBER = fakes.ROLES[0].id
TENANTMANAGER = fakes.ROLES[1].id


class TestIdentity(test.TestCase):
    def test_get_user(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_user(clients.identity, 'jim.spriggs@gmail.com')
        self.assertIsNotNone(
            identity.get_user(clients.identity, 'fred.nurke@gmail.com')
        )

    def test_get_user_by_id_or_name(self):
        clients = fakes.make_fake_clients()
        by_id = identity.get_user(clients.identity, FRED)
        by_name = identity.get_user(clients.identity, 'fred.nurke@gmail.com')
        self.assertIs(fakes.USERS[0], by_id)
        self.assertIs(by_id, by_name)

    def test_get_user_unknown(self):
        clients = fakes.make_fake_clients()
        out = self.capture_stdout()
        with self.assertRaises(NotFound):
            identity.get_user(clients.identity, 'jim.spriggs@gmail.com')
        self.assertEqual(
            'Unknown User jim.spriggs@gmail.com\n', out.getvalue()
        )
        self.assertEqual({}, identity.user_cache)

    def test_get_user_cache(self):
        clients = fakes.make_fake_clients()
        self.assertEqual({}, identity.user_cache)
        # Cache misses populate the cache (keyed by id)
        user = identity.get_user(
            clients.identity, 'fred.nurke@gmail.com', use_cache=True
        )
        self.assertEqual({FRED: user}, identity.user_cache)
        # Cache hits don't touch keystone
        mock_identity = Mock()
        self.assertIs(
            user, identity.get_user(mock_identity, FRED, use_cache=True)
        )
        mock_identity.users.get.assert_not_called()
        mock_identity.users.find.assert_not_called()
        # Only ids are cached; names go to keystone
        with self.assertRaises(NotFound):
            identity.get_user(
                clients.identity, 'jim.spriggs@gmail.com', use_cache=True
            )
        # Without use_cache the cache is bypassed (but still updated)
        mock_identity.users.get.return_value = fakes.USERS[1]
        self.assertIs(fakes.USERS[1], identity.get_user(mock_identity, FRED))
        mock_identity.users.get.assert_called_once_with(FRED)
        self.assertEqual(
            {FRED: user, TERRY: fakes.USERS[1]}, identity.user_cache
        )

    def test_get_project(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_project(clients.identity, 'route66')
        self.assertIsNotNone(identity.get_project(clients.identity, 'area54'))

    def test_get_project_by_id_or_name(self):
        clients = fakes.make_fake_clients()
        by_id = identity.get_project(clients.identity, AREA54)
        by_name = identity.get_project(clients.identity, 'area54')
        self.assertIs(fakes.PROJECTS[0], by_id)
        self.assertIs(by_id, by_name)

    def test_get_project_unknown(self):
        clients = fakes.make_fake_clients()
        out = self.capture_stdout()
        with self.assertRaises(NotFound):
            identity.get_project(clients.identity, 'route66')
        self.assertEqual('Unknown Project route66\n', out.getvalue())
        self.assertEqual({}, identity.project_cache)

    def test_get_project_cache(self):
        clients = fakes.make_fake_clients()
        self.assertEqual({}, identity.project_cache)
        project = identity.get_project(
            clients.identity, 'area54', use_cache=True
        )
        self.assertEqual({AREA54: project}, identity.project_cache)
        mock_identity = Mock()
        self.assertIs(
            project,
            identity.get_project(mock_identity, AREA54, use_cache=True),
        )
        mock_identity.projects.get.assert_not_called()
        mock_identity.projects.find.assert_not_called()
        with self.assertRaises(NotFound):
            identity.get_project(clients.identity, 'route66', use_cache=True)
        mock_identity.projects.get.return_value = fakes.PROJECTS[1]
        self.assertIs(
            fakes.PROJECTS[1], identity.get_project(mock_identity, AREA54)
        )
        self.assertEqual(
            {AREA54: project, SANANDREAS: fakes.PROJECTS[1]},
            identity.project_cache,
        )

    def test_get_roles(self):
        clients = fakes.make_fake_clients()
        self.assertIsNotNone(identity.get_role(clients.identity, 'member'))
        self.assertIsNotNone(
            identity.get_role(clients.identity, 'tenantmanager')
        )

    def test_get_role_not_found(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_role(clients.identity, 'admin')
        self.assertEqual({}, identity.role_cache)

    def test_get_role_cache(self):
        clients = fakes.make_fake_clients()
        role = identity.get_role(clients.identity, 'member')
        self.assertIs(fakes.ROLES[0], role)
        # Roles are always cached, by the requested name
        self.assertEqual({'member': role}, identity.role_cache)
        mock_identity = Mock()
        self.assertIs(role, identity.get_role(mock_identity, 'member'))
        mock_identity.roles.find.assert_not_called()
        # A different spelling is a different cache entry
        self.assertIs(role, identity.get_role(clients.identity, 'Member'))
        self.assertEqual({'member': role, 'Member': role}, identity.role_cache)

    def test_clear_caches(self):
        clients = fakes.make_fake_clients()
        identity.get_user(clients.identity, FRED)
        identity.get_project(clients.identity, AREA54)
        identity.get_role(clients.identity, 'member')
        self.assertTrue(identity.user_cache)
        self.assertTrue(identity.project_cache)
        self.assertTrue(identity.role_cache)
        identity.clear_caches()
        self.assertEqual({}, identity.user_cache)
        self.assertEqual({}, identity.project_cache)
        self.assertEqual({}, identity.role_cache)

    def test_list_all(self):
        clients = fakes.make_fake_clients(list_limit=2)
        self.assertEqual(
            fakes.USERS, identity.list_all(clients.identity.users.list)
        )
        clients = fakes.make_fake_clients(list_limit=1)
        self.assertEqual(
            fakes.PROJECTS, identity.list_all(clients.identity.projects.list)
        )

    def test_list_all_unpaginated(self):
        """Older keystones return the whole listing in one page"""
        clients = fakes.make_fake_clients()
        self.assertEqual(
            fakes.USERS, identity.list_all(clients.identity.users.list)
        )

    def test_list_all_empty(self):
        list_method = Mock(return_value=[])
        self.assertEqual([], identity.list_all(list_method))
        list_method.assert_called_once_with()

    def test_list_all_kwargs(self):
        list_method = Mock(side_effect=[[fakes.USERS[0]], []])
        self.assertEqual(
            [fakes.USERS[0]], identity.list_all(list_method, domain='d1')
        )
        self.assertEqual(
            [dict(domain='d1'), dict(marker=FRED, domain='d1')],
            [call.kwargs for call in list_method.call_args_list],
        )

    def test_list_all_marker_ignored(self):
        """A server that ignores the marker returns the same page
        again and again; don't loop forever.
        """
        page = fakes.USERS[:2]
        list_method = Mock(return_value=list(page))
        self.assertEqual(page, identity.list_all(list_method))
        self.assertEqual(2, list_method.call_count)

    def test_get_user_emails_with_roles(self):
        clients = fakes.make_fake_clients()
        emails = identity.get_user_emails_with_roles(
            clients.identity,
            project_id='44444444-1111-1111-1111-111111111111',
            role_names=['member', 'tenantmanager'],
        )
        self.assertEqual(
            ['terry.towling@gmail.com', 'fred.nurke@gmail.com'], emails
        )

    def test_get_user_emails_with_roles_order(self):
        """Emails come out in role order, without duplicates"""
        clients = fakes.make_fake_clients()
        emails = identity.get_user_emails_with_roles(
            clients.identity,
            project_id=AREA54,
            role_names=['tenantmanager', 'member'],
        )
        self.assertEqual(
            ['fred.nurke@gmail.com', 'terry.towling@gmail.com'], emails
        )

    def test_get_user_emails_with_roles_exclude_disabled(self):
        users = [
            fakes.FakeUser(
                id=FRED,
                name='fred.nurke@gmail.com',
                email='fred.nurke@gmail.com',
                full_name='Fred Nurke',
                enabled=False,
            )
        ] + fakes.USERS[1:]
        clients = fakes.make_fake_clients(users=users)
        self.assertEqual(
            ['terry.towling@gmail.com', 'fred.nurke@gmail.com'],
            identity.get_user_emails_with_roles(
                clients.identity, AREA54, ['member', 'tenantmanager']
            ),
        )
        self.assertEqual(
            ['terry.towling@gmail.com'],
            identity.get_user_emails_with_roles(
                clients.identity,
                AREA54,
                ['member', 'tenantmanager'],
                exclude_disabled=True,
            ),
        )

    def test_get_user_emails_with_roles_none(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            [],
            identity.get_user_emails_with_roles(
                clients.identity, TROVE, ['member', 'tenantmanager']
            ),
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

    def test_get_user_emails_by_role_only_requested_roles(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            {'tenantmanager': ['fred.nurke@gmail.com']},
            identity.get_user_emails_by_role(
                clients.identity, AREA54, ['tenantmanager']
            ),
        )

    def test_get_user_emails_by_role_ignores_groups(self):
        assignments = fakes.ASSIGNMENTS + [
            fakes.FakeRoleAssignment(
                group_id='group-1', project_id=AREA54, role_id=TENANTMANAGER
            ),
        ]
        clients = fakes.make_fake_clients(assignments=assignments)
        self.assertEqual(
            {
                'member': ['terry.towling@gmail.com', 'fred.nurke@gmail.com'],
                'tenantmanager': ['fred.nurke@gmail.com'],
            },
            identity.get_user_emails_by_role(
                clients.identity, AREA54, ['member', 'tenantmanager']
            ),
        )

    def test_get_user_emails_by_role_without_email(self):
        assignments = fakes.ASSIGNMENTS + [
            fakes.FakeRoleAssignment(
                user_id=TROVE_USER, project_id=AREA54, role_id=MEMBER
            ),
        ]
        clients = fakes.make_fake_clients(assignments=assignments)
        self.assertEqual(
            {'member': ['terry.towling@gmail.com', 'fred.nurke@gmail.com']},
            identity.get_user_emails_by_role(
                clients.identity, AREA54, ['member']
            ),
        )

    def test_get_user_emails_by_role_exclude_disabled(self):
        users = [
            fakes.FakeUser(
                id=FRED,
                name='fred.nurke@gmail.com',
                email='fred.nurke@gmail.com',
                full_name='Fred Nurke',
                enabled=False,
            )
        ] + fakes.USERS[1:]
        clients = fakes.make_fake_clients(users=users)
        self.assertEqual(
            {'member': ['terry.towling@gmail.com'], 'tenantmanager': []},
            identity.get_user_emails_by_role(
                clients.identity,
                AREA54,
                ['member', 'tenantmanager'],
                exclude_disabled=True,
            ),
        )

    def test_get_user_emails_by_role_unknown_role(self):
        clients = fakes.make_fake_clients()
        with self.assertRaises(NotFound):
            identity.get_user_emails_by_role(
                clients.identity, AREA54, ['member', 'admin']
            )

    def test_get_user_emails_by_role_no_assignments(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            {'member': [], 'tenantmanager': []},
            identity.get_user_emails_by_role(
                clients.identity, TROVE, ['member', 'tenantmanager']
            ),
        )

    def test_resolve_user_emails(self):
        clients = fakes.make_fake_clients()
        user_ids_by_role = {
            'TenantManager': [FRED, FRED, TROVE_USER],
            'Member': [TERRY, FRED, RANDY],
            'Other': [RANDY],
        }
        self.assertEqual(
            {
                'TenantManager': ['fred.nurke@gmail.com'],
                'Member': [
                    'terry.towling@gmail.com',
                    'fred.nurke@gmail.com',
                    'randy.katz@gmail.com',
                ],
                'Missing': [],
            },
            identity.resolve_user_emails(
                clients.identity,
                user_ids_by_role,
                ['TenantManager', 'Member', 'Missing'],
            ),
        )
        # The users are cached on the way through
        self.assertEqual(
            {FRED, TERRY, RANDY, TROVE_USER}, set(identity.user_cache)
        )

    def test_resolve_user_emails_exclude_disabled(self):
        users = [
            fakes.FakeUser(
                id=FRED,
                name='fred.nurke@gmail.com',
                email='fred.nurke@gmail.com',
                full_name='Fred Nurke',
                enabled=False,
            )
        ] + fakes.USERS[1:]
        clients = fakes.make_fake_clients(users=users)
        user_ids_by_role = {'Member': [FRED, TERRY]}
        self.assertEqual(
            {'Member': ['fred.nurke@gmail.com', 'terry.towling@gmail.com']},
            identity.resolve_user_emails(
                clients.identity, user_ids_by_role, ['Member']
            ),
        )
        self.assertEqual(
            {'Member': ['terry.towling@gmail.com']},
            identity.resolve_user_emails(
                clients.identity,
                user_ids_by_role,
                ['Member'],
                exclude_disabled=True,
            ),
        )

    def test_get_tenant_managers_emails(self):
        clients = fakes.make_fake_clients()
        # An instance in area54 ...
        self.assertEqual(
            ['fred.nurke@gmail.com'],
            identity.get_tenant_managers_emails(
                clients.identity, fakes.SERVERS[0]
            ),
        )
        # ... in sanandreas ...
        self.assertEqual(
            ['randy.katz@gmail.com'],
            identity.get_tenant_managers_emails(
                clients.identity, fakes.SERVERS[2]
            ),
        )
        # ... and in the trove project, which has no tenant managers
        self.assertEqual(
            [],
            identity.get_tenant_managers_emails(
                clients.identity, fakes.SERVERS[3]
            ),
        )

    def test_prefetch(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            len(fakes.USERS), identity.prefetch_users(clients.identity)
        )
        self.assertEqual(
            len(fakes.PROJECTS), identity.prefetch_projects(clients.identity)
        )
        self.assertIn(
            '33333333-1111-1111-1111-111111111111', identity.user_cache
        )
        self.assertIn(
            '44444444-1111-1111-1111-111111111111', identity.project_cache
        )

    def test_prefetch_populates_caches(self):
        clients = fakes.make_fake_clients()
        identity.prefetch_users(clients.identity)
        identity.prefetch_projects(clients.identity)
        self.assertEqual(
            {user.id: user for user in fakes.USERS}, identity.user_cache
        )
        self.assertEqual(
            {project.id: project for project in fakes.PROJECTS},
            identity.project_cache,
        )
        # Subsequent cached lookups don't go to keystone
        mock_identity = Mock()
        self.assertIs(
            fakes.USERS[0],
            identity.get_user(mock_identity, FRED, use_cache=True),
        )
        self.assertIs(
            fakes.PROJECTS[0],
            identity.get_project(mock_identity, AREA54, use_cache=True),
        )
        mock_identity.users.get.assert_not_called()
        mock_identity.projects.get.assert_not_called()

    def test_prefetch_paginated(self):
        """The prefetch must follow keystone's marker pagination when
        the server pages the listing (keystone >= 2025.1 'Epoxy').
        """
        clients = fakes.make_fake_clients(list_limit=2)
        self.assertEqual(
            len(fakes.USERS), identity.prefetch_users(clients.identity)
        )
        self.assertEqual(
            len(fakes.PROJECTS), identity.prefetch_projects(clients.identity)
        )

    def test_prefetch_empty(self):
        clients = fakes.make_fake_clients(users=[], projects=[])
        self.assertEqual(0, identity.prefetch_users(clients.identity))
        self.assertEqual(0, identity.prefetch_projects(clients.identity))
        self.assertEqual({}, identity.user_cache)
        self.assertEqual({}, identity.project_cache)

    def test_get_role_assignments_by_project(self):
        clients = fakes.make_fake_clients()
        assignments = identity.get_role_assignments_by_project(
            clients.identity, ['TenantManager', 'Member']
        )
        self.assertEqual(
            {
                '44444444-1111-1111-1111-111111111111': {
                    'TenantManager': ['33333333-1111-1111-1111-111111111111'],
                    'Member': [
                        '33333333-1111-1111-1111-111111111112',
                        '33333333-1111-1111-1111-111111111111',
                    ],
                },
                '44444444-1111-1111-1111-111111111112': {
                    'TenantManager': ['33333333-1111-1111-1111-111111111113'],
                    'Member': ['33333333-1111-1111-1111-111111111113'],
                },
            },
            assignments,
        )

    def test_get_role_assignments_by_project_one_role(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            {
                AREA54: {'tenantmanager': [FRED]},
                SANANDREAS: {'tenantmanager': [RANDY]},
            },
            identity.get_role_assignments_by_project(
                clients.identity, ['tenantmanager']
            ),
        )

    def test_get_role_assignments_by_project_no_roles(self):
        clients = fakes.make_fake_clients()
        self.assertEqual(
            {},
            identity.get_role_assignments_by_project(clients.identity, []),
        )

    def test_get_role_assignments_by_project_ignores_groups_and_domains(
        self,
    ):
        assignments = fakes.ASSIGNMENTS + [
            # A group assignment
            fakes.FakeRoleAssignment(
                group_id='group-1', project_id=AREA54, role_id=TENANTMANAGER
            ),
            # A domain scoped user assignment
            fakes.FakeRoleAssignment(
                user_id=TERRY, domain_id='default', role_id=TENANTMANAGER
            ),
            # A domain scoped group assignment
            fakes.FakeRoleAssignment(
                group_id='group-1', domain_id='default', role_id=MEMBER
            ),
        ]
        clients = fakes.make_fake_clients(assignments=assignments)
        self.assertEqual(
            {
                AREA54: {'TenantManager': [FRED], 'Member': [TERRY, FRED]},
                SANANDREAS: {'TenantManager': [RANDY], 'Member': [RANDY]},
            },
            identity.get_role_assignments_by_project(
                clients.identity, ['TenantManager', 'Member']
            ),
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
