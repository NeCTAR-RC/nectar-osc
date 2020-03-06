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

try:
    from freshdesk.v2.api import API
except ImportError:
    API = None


def get_config(api_key=None,
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


def get_client(domain, api_key):
    if not API:
        print("To use this tool, you will need to also install the"
              "python-freshdesk package: \n"
              "  $ pip install python-freshdesk")
        exit(1)
    return API(domain, api_key)
