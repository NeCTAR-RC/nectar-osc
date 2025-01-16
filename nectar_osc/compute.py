# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

import collections
import json

from openstackclient.compute.v2 import server as osc_server
from oslo_config import cfg
from prettytable import PrettyTable

from nectar_osc.identity import get_project
from nectar_osc.identity import get_user

CONF = cfg.CONF


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
        if v and isinstance(v, str) and (r'\n' in v or '\r' in v):
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
                'border': '1',
                'style': 'border-width: 1px; border-collapse: collapse;',
            }
        )
    else:
        output = 'Instance details:\n'
        output += pt.get_string()
    return output


def show_instance(clients, instance_id, style=None):
    instance = clients.compute.get_server(instance_id)
    data = osc_server._prep_server_detail(
        clients.compute, clients.image, instance, refresh=False
    )

    return _format_instance(data, style=style)


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
        server_info['host'] = server['OS-EXT-SRV-ATTR:host']
        server_info['full_host'] = server[
            'OS-EXT-SRV-ATTR:hypervisor_hostname'
        ]
        server_info['zone'] = server['OS-EXT-AZ:availability_zone']

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
            server_info['project'] = server.project_id

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


def all_instances(clients, **kwargs):
    return InstanceExtractor(clients, **kwargs).all()


class ReachedLimit(Exception):
    pass


class InstanceExtractor:
    def __init__(
        self,
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
        self.clients = clients
        self.zones = zones
        self.hosts = hosts
        self.status = status
        self.ips = ips
        self.image_id = image_id
        self.project_id = project_id
        self.user_id = user_id
        self.limit = limit

    def get_opts(self):
        opts = {"all_projects": True}
        if self.status and self.status != 'ALL':
            opts['status'] = self.status
        if CONF.nova.page_size > 0:
            opts['limit'] = CONF.nova.page_size
        if self.image_id:
            opts['image'] = self.image_id
        if self.user_id:
            opts['user_id'] = self.user_id
        if self.project_id:
            opts['project_id'] = self.project_id
        return opts

    def all(self):
        self.res = []
        self.count = 0

        try:
            # When using all the searching opts other than project or user,
            # trove instances will be returned by default via nova list api.
            # But they will not when search_opts contain project or user.
            # In order to include them, searching all the instances under
            # project "trove" and filtering them by the instance metadata.
            if self.project_id or self.user_id:
                for server in self._trove_instances():
                    self._final_processing(server)

            if self.hosts:
                for host in self.hosts:
                    for server in self._host_instances(host):
                        self._final_processing(server)
            else:
                for server in self._instances():
                    self._final_processing(server)
        except ReachedLimit:
            pass
        return self.res

    def _final_processing(self, server):
        if self.limit and self.count >= self.limit:
            raise ReachedLimit()
        if self._match_az(server) and self._match_ip_address(server):
            self.res.append(extract_server_info(self.clients, server=server))
            self.count += 1

    def _instances(self, opts=None):
        """Generate all instances matching search criteria 'opts'

        When 'opts' is not supplied, generate them.  The generator
        deals with paging through the servers returned by Nova.
        """

        if opts is None:
            opts = self.get_opts()
        marker = None
        while True:
            if marker:
                opts['marker'] = marker
            instances = list(self.clients.compute.servers(**opts))
            if not instances:
                break
            # for some instances stuck in build phase, servers.list api
            # will always return the marker instance. Add old marker and
            # new marker comparison to avoid the dead loop
            marker_new = instances[-1].id
            if marker == marker_new:
                break
            marker = marker_new

            yield from instances

    def _host_instances(self, host):
        opts = self.get_opts()
        opts['compute_host'] = host
        yield from self._instances(opts)

    def _trove_instances(self):
        opts = self.get_opts()
        opts.pop('user_id', None)
        opts['project_id'] = get_project(self.clients.identity, 'trove').id
        for server in self._instances(opts):
            if self._match_proj_user(server):
                yield server

    def _match_proj_user(self, server):
        if self.project_id:
            if (
                getattr(server, 'metadata').get("project_id")
                != self.project_id
            ):
                return False
        if self.user_id:
            if getattr(server, 'metadata').get("user_id") != self.user_id:
                return False
        return True

    def _match_az(self, server):
        if self.zones:
            return server["OS-EXT-AZ:availability_zone"] in self.zones
        else:
            return True

    def _match_ip_address(self, server):
        if not self.ips:
            return True
        for ip in self.ips:
            if any(
                map(
                    lambda a: any(map(lambda aa: ip in aa['addr'], a)),
                    server.addresses.values(),
                )
            ):
                return True
        return False
