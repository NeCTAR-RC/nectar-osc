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


def clear_caches():
    """Clear the project, user and role caches"""
    project_cache.clear()
    user_cache.clear()
    role_cache.clear()


def get_role(identity, role_name):
    """Fetch project via the cache"""
    if role_name in role_cache:
        return role_cache[role_name]
    else:
        role = identity.roles.find(name=role_name)
        role_cache[role_name] = role
        return role


def list_all(list_method, **kwargs):
    """List all resources of a paginated keystone collection.

    Since 2025.1 (Epoxy) keystone paginates list responses, returning
    at most its configured page size (default 1000) of results per
    request.  Follow the marker pagination until a page comes back
    empty to collect the complete listing.
    """
    results = list_method(**kwargs)
    page = results
    while page:
        marker = page[-1].id
        page = list_method(marker=marker, **kwargs)
        if page and page[-1].id == marker:
            # The server does not understand marker paging and has
            # returned the same page again.  Avoid looping forever.
            break
        results.extend(page)
    return results


def prefetch_users(identity):
    """Populate the user cache with all users.

    Cache misses still fall back to a per-user query, so this is
    purely an optimization.
    """
    users = list_all(identity.users.list)
    for user in users:
        user_cache[user.id] = user
    return len(users)


def prefetch_projects(identity):
    """Populate the project cache with all projects.

    Cache misses still fall back to a per-project query, so this is
    purely an optimization.
    """
    projects = list_all(identity.projects.list)
    for project in projects:
        project_cache[project.id] = project
    return len(projects)


def get_role_assignments_by_project(identity, role_names):
    """Fetch the user role assignments for the named roles across
    all projects, with one role-assignment query per role.

    Returns a dict mapping project id to a dict mapping role name
    to a list of user ids.  Roles assigned to groups rather than
    users are ignored, as are non project-scoped assignments.
    """
    result = {}
    for role_name in role_names:
        role = get_role(identity, role_name)
        for ra in identity.role_assignments.list(role=role):
            if not hasattr(ra, 'user'):
                continue
            project_id = ra.scope.get('project', {}).get('id')
            if not project_id:
                continue
            result.setdefault(project_id, {}).setdefault(role_name, []).append(
                ra.user['id']
            )
    return result


def resolve_user_emails(
    identity, user_ids_by_role, role_names, exclude_disabled=False
):
    """Resolve user ids, grouped by role name, to email addresses.

    Returns a dict mapping each role name to a list of email
    addresses.  Users without an email (and optionally disabled
    users) are excluded.
    """
    emails = {role_name: [] for role_name in role_names}
    for role_name in role_names:
        for user_id in user_ids_by_role.get(role_name, []):
            u = get_user(identity, user_id, use_cache=True)
            if exclude_disabled and not u.enabled:
                continue
            email = getattr(u, 'email', None)
            if email and email not in emails[role_name]:
                emails[role_name].append(email)
    return emails


def get_user_emails_by_role(
    identity, project_id, role_names, exclude_disabled=False
):
    """Get email addresses for users with certain roles
    in a given project, as a dict mapping each role name to a
    list of email addresses.

    A single role-assignment query is made for the project; the
    requested roles are selected client-side by role id.  (Matching
    by id rather than name is important: keystone resolves role
    names case-insensitively, so the stored name's case may differ
    from the requested one.)  Roles assigned to groups rather than
    users are ignored.
    """
    role_ids = {
        get_role(identity, role_name).id: role_name for role_name in role_names
    }
    user_ids_by_role = {}
    for ra in identity.role_assignments.list(project=project_id):
        if not hasattr(ra, 'user'):
            continue
        role_name = role_ids.get(ra.role['id'])
        if role_name is None:
            continue
        user_ids_by_role.setdefault(role_name, []).append(ra.user['id'])
    return resolve_user_emails(
        identity, user_ids_by_role, role_names, exclude_disabled
    )


def get_user_emails_with_roles(
    identity, project_id, role_names, exclude_disabled=False
):
    """Get email addresses for users with certain roles
    in a given project."""
    by_role = get_user_emails_by_role(
        identity, project_id, role_names, exclude_disabled
    )
    emails = []
    for role_name in role_names:
        for email in by_role[role_name]:
            if email not in emails:
                emails.append(email)
    return emails


def get_tenant_managers_emails(identity, instance):
    """Get tenant manager emails for an instance."""

    return get_user_emails_with_roles(
        identity, instance.project_id, ['TenantManager']
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
