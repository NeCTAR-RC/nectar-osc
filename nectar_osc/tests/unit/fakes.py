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

from collections import defaultdict

import keystoneauth1
import keystoneclient
import novaclient


# Fake osc clients for identity and compute.


class FakeClients:
    def __init__(self, compute=None, identity=None, taynac=None):
        self.compute = compute or FakeCompute()
        self.identity = identity or FakeIdentity()
        self.taynac = taynac


class FakeIdentity:
    def __init__(self, users=[], projects=[], roles=[], assignments=[]):
        self.users = FakeUsers(users)
        self.projects = FakeProjects(projects)
        self.roles = FakeRoles(roles)
        self.role_assignments = FakeRoleAssignments(assignments)
        for obj in assignments:
            setattr(obj, 'identity', self)


class FakeUsers:
    def __init__(self, users=[]):
        self.users = users

    def get(self, id):
        for user in self.users:
            if user.id == id:
                return user
        raise keystoneauth1.exceptions.http.NotFound()

    def find(self, name):
        for user in self.users:
            if user.id == name or user.name == name:
                return user
        raise keystoneauth1.exceptions.http.NotFound()


class FakeUser:
    def __init__(self, id, name, email, full_name, enabled=True):
        self.id = id
        self.name = name
        self.email = email
        self.full_name = full_name
        self.enabled = enabled

    def __getitem__(self, key):
        return getattr(self, key)


class FakeRoles:
    def __init__(self, roles=[]):
        self.roles = roles

    def get(self, id):
        for role in self.roles:
            if role.id == id:
                return role
        raise keystoneauth1.exceptions.http.NotFound()

    def find(self, name):
        for role in self.roles:
            if role.id == name or role.name == name:
                return role
        raise keystoneauth1.exceptions.http.NotFound()


class FakeRole:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeProjects:
    def __init__(self, projects=[]):
        self.projects = projects

    def get(self, id):
        for project in self.projects:
            if project.id == id:
                return project
        raise keystoneclient.exceptions.NotFound(404)

    def find(self, name):
        for project in self.projects:
            if project.id == name or project.name == name:
                return project
        raise keystoneauth1.exceptions.http.NotFound()


class FakeProject:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeRoleAssignments:
    def __init__(self, assignments=[]):
        self.assignments = assignments

    def list(self, project, role, include_names):
        return [
            ra
            for ra in self.assignments
            if project == ra.project and role == ra.role
        ]


class FakeRoleAssignment:
    def __init__(self, project_id, role_id, user_id):
        self.project = project_id
        self.role_id = role_id
        self.user_id = user_id

    def __getattr__(self, name):
        if name == 'role':
            return self.identity.roles.get(self.role_id)
        elif name == 'user':
            return self.identity.users.get(self.user_id)
        else:
            raise AttributeError(name)


class FakeCompute:
    def __init__(self, servers=[], max_response=None):
        self.servers = FakeServers(servers, max_response)


class FakeServers:
    def __init__(self, servers=[], max_response=None):
        self.servers = servers
        self.max_response = max_response

    def get(self, id):
        for server in self.servers:
            if server.id == id:
                return server
        raise novaclient.exceptions.NotFound(404)

    def list(self, search_opts):
        res = []
        limit_opt = search_opts.get('limit', None)
        limit = int(limit_opt) if limit_opt else 0
        user_id = search_opts.get('user_id', None)
        tenant_id = search_opts.get('tenant_id', None)
        status = search_opts.get('status', None)
        image = search_opts.get('image', None)
        host = search_opts.get('host', None)
        marker = search_opts.get('marker', None)
        for server in self.servers:
            if marker:
                # Skipping to first server *after* the marker
                if marker == server.id:
                    marker = None
                continue
            if limit and limit <= len(res):
                break
            if self.max_response and self.max_response <= len(res):
                break
            if user_id and user_id != server.user_id:
                continue
            if tenant_id and tenant_id != server.tenant_id:
                continue
            if status and status != server.status:
                continue
            if image and image != server.image:
                continue
            if host and host != server.host:
                continue
            res.append(server)
        return res


class FakeServer:
    def __init__(
        self,
        id,
        name,
        status,
        flavor,
        host,
        zone,
        image,
        metadata,
        addresses,
        user_id,
        tenant_id,
    ):
        self.id = id
        self.name = name
        self.status = status
        self.flavor = flavor
        self.host = host
        setattr(self, 'OS-EXT-SRV-ATTR:host', host)
        setattr(self, 'OS-EXT-AZ:availability_zone', zone)
        self.image = image
        self.metadata = metadata
        self.addresses = addresses
        self.user_id = user_id
        self.tenant_id = tenant_id

    def to_dict(self):
        return defaultdict(dict, vars(self))


# Common test data
SERVERS = [
    FakeServer(
        id='00000000-1111-1111-1111-111111111111',
        name='one',
        status='STOPPED',
        flavor={'id': '11111111-1111-1111-1111-111111111111', 'name': 'lemon'},
        host='cn1.twilight.nectar.org.au',
        zone='twilight',
        image={'id': '22222222-1111-1111-1111-111111111111'},
        metadata={
            'user_id': '33333333-1111-1111-1111-111111111111',
            'project_id': '44444444-1111-1111-1111-111111111111',
        },
        addresses={
            'net_name': [
                {
                    'addr': '192.168.76.119',
                }
            ]
        },
        user_id='33333333-1111-1111-1111-111111111111',
        tenant_id='44444444-1111-1111-1111-111111111111',
    ),
    FakeServer(
        id='00000000-1111-1111-1111-111111111112',
        name='two',
        status='ACTIVE',
        flavor={'id': '11111111-1111-1111-1111-111111111111', 'name': 'lemon'},
        host='cn1.danger.nectar.org.au',
        zone='danger',
        image={'id': '22222222-1111-1111-1111-111111111112'},
        metadata={
            'user_id': '33333333-1111-1111-1111-111111111111',
            'project_id': '44444444-1111-1111-1111-111111111111',
        },
        addresses={
            'net_name': [
                {
                    'addr': '192.168.76.112',
                }
            ]
        },
        user_id='33333333-1111-1111-1111-111111111111',
        tenant_id='44444444-1111-1111-1111-111111111111',
    ),
    FakeServer(
        id='00000000-1111-1111-1111-111111111113',
        name='three',
        status='ACTIVE',
        flavor={'id': '11111111-1111-1111-1111-111111111111', 'name': 'lemon'},
        host='cn2.danger.nectar.org.au',
        zone='danger',
        image={'id': '22222222-1111-1111-1111-111111111112'},
        metadata={
            'user_id': '33333333-1111-1111-1111-111111111113',
            'project_id': '44444444-1111-1111-1111-111111111112',
        },
        addresses={
            'net_name': [
                {
                    'addr': '192.168.76.123',
                }
            ]
        },
        user_id='33333333-1111-1111-1111-111111111113',
        tenant_id='44444444-1111-1111-1111-111111111112',
    ),
]

PROJECTS = [
    FakeProject(id='44444444-1111-1111-1111-111111111111', name='area54'),
    FakeProject(id='44444444-1111-1111-1111-111111111112', name='sanandreas'),
]

USERS = [
    FakeUser(
        id='33333333-1111-1111-1111-111111111111',
        name='fred.nurke@gmail.com',
        email='fred.nurke@gmail.com',
        full_name='Fred Nurke',
    ),
    FakeUser(
        id='33333333-1111-1111-1111-111111111112',
        name='terry.towling@gmail.com',
        email='terry.towling@gmail.com',
        full_name='Terrance Towling',
    ),
    FakeUser(
        id='33333333-1111-1111-1111-111111111113',
        name='randy.katz@gmail.com',
        email='randy.katz@gmail.com',
        full_name='Randolph Katz',
    ),
]

ROLES = [
    FakeRole(
        id='77777777-1111-11111-1111-111111111111',
        name='Member',
    ),
    FakeRole(
        id='77777777-1111-11111-1111-111111111112',
        name='TenantManager',
    ),
]


ASSIGNMENTS = [
    FakeRoleAssignment(
        user_id='33333333-1111-1111-1111-111111111112',
        project_id='44444444-1111-1111-1111-111111111111',
        role_id='77777777-1111-11111-1111-111111111111',
    ),
    FakeRoleAssignment(
        user_id='33333333-1111-1111-1111-111111111111',
        project_id='44444444-1111-1111-1111-111111111111',
        role_id='77777777-1111-11111-1111-111111111111',
    ),
    FakeRoleAssignment(
        user_id='33333333-1111-1111-1111-111111111111',
        project_id='44444444-1111-1111-1111-111111111111',
        role_id='77777777-1111-11111-1111-111111111112',
    ),
    FakeRoleAssignment(
        user_id='33333333-1111-1111-1111-111111111113',
        project_id='44444444-1111-1111-1111-111111111112',
        role_id='77777777-1111-11111-1111-111111111111',
    ),
    FakeRoleAssignment(
        user_id='33333333-1111-1111-1111-111111111113',
        project_id='44444444-1111-1111-1111-111111111112',
        role_id='77777777-1111-11111-1111-111111111112',
    ),
]


def make_fake_clients(
    users=USERS,
    projects=PROJECTS,
    servers=SERVERS,
    roles=ROLES,
    assignments=ASSIGNMENTS,
    max_response=None,
    taynac=None,
):
    return FakeClients(
        compute=FakeCompute(servers=servers, max_response=max_response),
        identity=FakeIdentity(
            users=users,
            projects=projects,
            roles=roles,
            assignments=assignments,
        ),
        taynac=taynac,
    )
