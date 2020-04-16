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

import json
import six
import sys

from novaclient import exceptions as n_exc
from prettytable import PrettyTable


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
        output += pt.get_html_string(attributes={
            'border': 1,
            'style': 'border-width: 1px; border-collapse: collapse;'
        })
    else:
        output = 'Instance details:\n'
        output += pt.get_string()
    return output


def show_instance(clients, instance_id, style=None):
    try:
        instance = clients.compute.servers.get(instance_id)
    except n_exc.NotFound:
        print("Instance {} not found".format(instance_id))
        sys.exit(1)

    info = instance._info.copy()
    for network_label, address_list in instance.networks.items():
        info['%s network' % network_label] = ', '.join(address_list)

    flavor = info.get('flavor', {})
    flavor_id = flavor.get('id', '')

    try:
        info['flavor'] = '%s (%s)' % (
            clients.compute.flavors.get(flavor_id).name, flavor_id)
    except Exception:
        info['flavor'] = '%s (%s)' % ("Flavor not found", flavor_id)

    # Image
    image = info.get('image', {})
    if image:
        image_id = image.get('id', '')
        try:
            img = clients.image.images.get(image_id)
            nectar_build = img.get('nectar_build', 'N/A')
            info['image'] = ('%s (%s, NeCTAR Build %s)'
                             % (img.name, img.id, nectar_build))
        except Exception:
            info['image'] = 'Image not found (%s)' % image_id

    else:  # Booted from volume
        info['image'] = "Attempt to boot from volume - no image supplied"

    # Tenant
    project_id = info.get('tenant_id')
    if project_id:
        try:
            project = clients.identity.projects.get(project_id)
            info['tenant_id'] = '%s (%s)' % (project.name, project.id)
        except Exception:
            pass

    # User
    user_id = info.get('user_id')
    if user_id:
        try:
            user = clients.identity.users.get(user_id)
            info['user_id'] = '%s (%s)' % (user.name, user.id)
        except Exception:
            pass

    # Remove stuff
    info.pop('links', None)
    info.pop('addresses', None)
    info.pop('hostId', None)
    info.pop('security_groups', None)

    return _format_instance(info, style=style)
