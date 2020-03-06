from osc_lib import utils as osc_utils
from nectar_osc import lister

try:
    from freshdesk.v2.api import API
except ImportError:
    API = None


def get_freshdesk_config(api_key=None,
                         email_config_id=None,
                         group_id=None,
                         domain=None):
    """fetch freshdesk API details from config file"""
    msg = '\n'.join([
        'No Freshdesk details found in your config file.',
        '',
        'To find your Freshdesk API key by following the guide here:',
        'https://support.freshdesk.com/support/solutions/'
        'articles/215517-how-to-find-your-api-key',
        '',
        'Then add the following config to your configuration',
        'file (~/.nectar.conf):',
        '',
        '  [security]',
        '  api_key = <your api key>',
        '  email_config_id = <id>',
        '  group_id = <id>',
        '  domain = <domainname>',
    ])

    if api_key is None or email_config_id is None or \
        group_id is None or domain is None:
        print(msg)
        exit(1)

    fd_conf = {'api_key': api_key,
              'email_config_id': email_config_id,
              'group_id': group_id,
              'domain': domain}

    return(fd_conf)


def get_freshdesk_client(domain, api_key):
    if not API:
        print("To use this tool, you will need to also install the"
              "python-freshdesk package: \n"
              "  $ pip install python-freshdesk")
        exit(1)
    return API(domain, api_key)


def get_tenant_managers_emails(clients, instance):
    """Build a list of email addresses"""
    email_addresses = []
    project = clients.identity.projects.get(instance.tenant_id)
    role = clients.identity.roles.find(name='TenantManager')
    ras = clients.identity.role_assignments.list(project=project,
                                                role=role, include_names=True)
    for ra in ras:
        u = clients.identity.users.get(ra.user['id'])
        email_addresses.append(u.email)
    return email_addresses


def lockinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))


def unlockinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))


def deleteinstance(clients, args, config):
    instance = clients.compute.servers.get(args.id)
    print(lister.show_instance(clients, instance.id))
    print(lister.show_sg_groups(clients, instance.id))
