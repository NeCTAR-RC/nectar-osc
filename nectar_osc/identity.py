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


def get_tenant_managers_emails(identity, instance):
    """Build a list of email addresses"""
    email_addresses = []
    project = identity.projects.get(instance.tenant_id)
    role = identity.roles.find(name='TenantManager')
    ras = identity.role_assignments.list(project=project,
                                         role=role, include_names=True)
    for ra in ras:
        u = identity.users.get(ra.user['id'])
        email_addresses.append(u.email)
    return email_addresses
