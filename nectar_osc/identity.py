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

from keystoneclient.exceptions import NotFound

# global session cache for project, role and user query data
project_cache = {}
user_cache = {}
role_cache = {}


def get_role(identity, role_name):
    """Fetch project via the cache"""
    if role_name in role_cache:
        return role_cache[role_name]
    else:
        role = identity.roles.find(name=role_name)
        role_cache[role_name] = role
        return role


def get_user_emails_with_roles(
    identity, project_id, role_names, exclude_disabled=False
):
    """Get email addresses for users with certain roles
    in a given project."""
    emails = []
    for role_name in role_names:
        role = get_role(identity, role_name)
        ras = identity.role_assignments.list(
            project=project_id, role=role, include_names=True
        )
        for ra in ras:
            u = get_user(identity, ra.user['id'], use_cache=False)
            if exclude_disabled and not u.enabled:
                continue
            email = getattr(u, 'email', None)
            if email and email not in emails:
                emails.append(email)
    return emails


def get_tenant_managers_emails(identity, instance):
    """Get tenant manager emails for an instance."""
    return get_user_emails_with_roles(
        identity, instance.tenant_id, ['TenantManager']
    )


def get_project(identity, name_or_id, use_cache=False):
    """Fetch project, optionally via the cache"""
    if use_cache and name_or_id in project_cache:
        project = project_cache[name_or_id]
    else:
        try:
            project = None
            project = identity.projects.get(name_or_id)
        except NotFound:
            project = identity.projects.find(name=name_or_id)
        finally:
            if project:
                project_cache.update({project.id: project})
            else:
                # TODO(SC) bad idea ...
                print(f"Unknown Project {name_or_id}")
    return project


def get_user(identity, name_or_id, use_cache=False):
    """Fetch user, optionally via the cache"""
    if use_cache and name_or_id in user_cache:
        user = user_cache[name_or_id]
    else:
        try:
            user = None
            user = identity.users.get(name_or_id)
        except NotFound:
            user = identity.users.find(name=name_or_id)
        finally:
            if user:
                user_cache.update({user.id: user})
            else:
                # TODO(SC) bad idea ...
                print(f"Unknown User {name_or_id}")
    return user
