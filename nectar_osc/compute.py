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

import collections
import json
import six
import sys

from novaclient import exceptions as n_exc
from prettytable import PrettyTable

from nectar_osc.identity import get_project
from nectar_osc.identity import get_user


def _format_instance(d, style=None):
    """Pretty print instance info for the command line"""
    pt = PrettyTable(['Property', 'Value'], caching=False)
    pt.align = 'l'
    for k, v in sorted(d.items()):
        # convert dict to str to check length
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        # if value has a newline, add in multiple rows
        # e.g. fault with stacktrace
        if v and isinstance(v, six.string_types) and (r'\n' in v or '\r' in v):
            # '\r' would break the table, so remove it.
            if '\r' in v:
                v = v.replace('\r', '')
            lines = v.strip().split(r'\n')
            col1 = k
            for line in lines:
                pt.add_row([col1, line])
                col1 = ''
        else:
            if v is None:
                v = '-'
            pt.add_row([k, v])

    if style == 'html':
        output = '<b>Instance details</b>'
        output += pt.get_html_string(
            attributes={
                'border': 1,
                'style': 'border-width: 1px; border-collapse: collapse;',
            }
        )
    else:
        output = 'Instance details:\n'
        output += pt.get_string()
    return output


def show_instance(clients, instance_id, style=None):
    try:
        instance = clients.compute.servers.get(instance_id)
    except n_exc.NotFound:
        print(f"Instance {instance_id} not found")
        sys.exit(1)

    info = instance._info.copy()
    for network_label, address_list in instance.networks.items():
        info[f'{network_label} network'] = ', '.join(address_list)

    flavor = info.get('flavor', {})
    flavor_id = flavor.get('id', '')

    try:
        info['flavor'] = (
            f'{clients.compute.flavors.get(flavor_id).name} ({flavor_id})'
        )
    except Exception:
        info['flavor'] = '{} ({})'.format("Flavor not found", flavor_id)

    # Image
    image = info.get('image', {})
    if image:
        image_id = image.get('id', '')
        try:
            img = clients.image.images.get(image_id)
            nectar_build = img.get('nectar_build', 'N/A')
            info['image'] = (
                f'{img.name} ({img.id}, NeCTAR Build {nectar_build})'
            )
        except Exception:
            info['image'] = f'Image not found ({image_id})'

    else:  # Booted from volume
        info['image'] = "Attempt to boot from volume - no image supplied"

    # Tenant
    project_id = info.get('tenant_id')
    if project_id:
        try:
            project = clients.identity.projects.get(project_id)
            info['tenant_id'] = f'{project.name} ({project.id})'
        except Exception:
            pass

    # User
    user_id = info.get('user_id')
    if user_id:
        try:
            user = clients.identity.users.get(user_id)
            info['user_id'] = f'{user.name} ({user.id})'
        except Exception:
            pass

    # Remove stuff
    info.pop('links', None)
    info.pop('addresses', None)
    info.pop('hostId', None)
    info.pop('security_groups', None)

    return _format_instance(info, style=style)


def extract_server_info(clients, server):
    """Extract server information for mailout.

    Extract and massage information about a server, the user that
    launched it, its project and its image.  Return the information
    as a dictionary.
    """

    server_info = collections.defaultdict(dict)
    identity = clients.identity
    try:
        server_info['id'] = server.id
        server_info['name'] = server.name
        server_info['status'] = server.status

        server_info['flavor'] = server.flavor['id']
        server_info['host'] = getattr(server, "OS-EXT-SRV-ATTR:host")
        server_info['zone'] = getattr(server, "OS-EXT-AZ:availability_zone")

        # handle instances which are not booted from glance images
        server_image = getattr(server, "image", None)
        if server_image:
            server_info['image'] = server_image.get("id", None)
        else:
            server_info['image'] = None

        # handle some tier2 services which using a "global"
        # service user and project
        if (
            server.metadata
            and 'user_id' in server.metadata.keys()
            and 'project_id' in server.metadata.keys()
        ):
            server_info['user'] = server.metadata['user_id']
            server_info['project'] = server.metadata['project_id']
        else:
            server_info['user'] = server.user_id
            server_info['project'] = server.tenant_id

        server_info['addresses'] = _extract_ip(server)

        project = get_project(identity, server_info['project'], use_cache=True)
        server_info['project_name'] = project.name

        user = get_user(identity, server_info['user'], use_cache=True)

        # Handle instances created by jenkins/tempest and users without
        # a fullname.  Also set disabled user's email/fullname as None
        # so that we don't notify them.  (SC - revisit this logic.)
        if not user.enabled:
            server_info['email'] = None
            server_info['fullname'] = None
        elif getattr(user, 'email', None):
            server_info['email'] = user.email
            server_info['fullname'] = getattr(user, 'full_name', None)
        else:
            server_info['email'] = user.name
            server_info['fullname'] = None
    except KeyError as e:
        raise type(e)(f'{e.message} missing in context: {server.to_dict()}')
    return server_info


def _extract_ip(server):
    addresses = set()
    for addrs in server.addresses.values():
        for addr in addrs:
            if addr['addr']:
                addresses.add(addr['addr'])
    return list(addresses)


def all_instances(
    clients,
    zones=None,
    hosts=None,
    status=None,
    ips=None,
    image_id=None,
    project_id=None,
    user_id=None,
    limit=None,
):
    # TODO(SC) - The limit is loosely enforced
    marker = None
    opts = {}
    opts["all_tenants"] = True
    if status and status != 'ALL':
        opts['status'] = status
    if limit:
        opts['limit'] = limit
    if image_id:
        opts['image'] = image_id
    if user_id:
        opts['user_id'] = user_id
    if project_id:
        opts['tenant_id'] = project_id

    # When using all the searching opts other than project or user,
    # trove instances will be returned by default via nova list api.
    # But they will not when search_opts contain project or user.
    # In order to include them, searching all the instances under
    # project "trove" and filtering them by the instance metadata.
    if project_id or user_id:
        # TODO(SC) - consider the 'limit' ...
        inst = _search_trove_instances(clients, opts)
    else:
        inst = []

    if hosts:
        for host in hosts:
            opts['host'] = host
            instances = clients.compute.servers.list(search_opts=opts)
            if not instances:
                continue
            instances = filter(
                lambda x: _match_availability_zone(x, zones), instances
            )
            instances = filter(lambda x: _match_ip_address(x, ips), instances)
            inst.extend(instances)
            if limit and len(inst) >= int(limit):
                break
    else:
        while True:
            if marker:
                opts['marker'] = marker
            instances = clients.compute.servers.list(search_opts=opts)
            if not instances:
                break
            # for some instances stuck in build phase, servers.list api
            # will always return the marker instance. Add old marker and
            # new marker comparison to avoid the dead loop
            marker_new = instances[-1].id
            if marker == marker_new:
                break
            marker = marker_new
            instances = filter(
                lambda x: _match_availability_zone(x, zones), instances
            )
            instances = filter(lambda x: _match_ip_address(x, ips), instances)
            if not instances:
                continue
            inst.extend(instances)
            if limit and len(inst) >= int(limit):
                break

    return [extract_server_info(clients, server=server) for server in inst]


def _search_trove_instances(clients, opts):
    # keep the proj/user from searching opts
    proj_id = opts.get('tenant_id', None)
    user_id = opts.get('user_id', None)

    # trove instances will be launched by global trove project
    trove_opts = opts.copy()
    trove_opts.pop('user_id', None)
    trove_opts['tenant_id'] = clients.identity.projects.get('trove').id
    trove_instances = clients.compute.servers.list(search_opts=trove_opts)
    trove_instances = [
        instance
        for instance in trove_instances
        if _match_proj_user(instance, proj_id, user_id)
    ]
    return trove_instances


def _match_proj_user(server, proj_id=None, user_id=None):
    # server.metadata will return dict containing user's projectid and userid
    if proj_id:
        if getattr(server, 'metadata').get("project_id") != proj_id:
            return False
    if user_id:
        if getattr(server, 'metadata').get("user_id") != user_id:
            return False
    return True


def _match_availability_zone(server, az=None):
    if az:
        if getattr(server, "OS-EXT-AZ:availability_zone") not in az:
            return False
    return True


def _match_ip_address(server, ips):
    if not ips:
        return True
    for ip in ips:
        if any(
            map(
                lambda a: any(map(lambda aa: ip in aa['addr'], a)),
                server.addresses.values(),
            )
        ):
            return True
    return False
