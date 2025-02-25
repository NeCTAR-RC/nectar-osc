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

from datetime import datetime
from datetime import timedelta
import logging
import os
import shutil
import sys
import tempfile
import yaml

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import Template

from osc_lib.command import command
from oslo_config import cfg

from nectar_osc.compute import all_instances
from nectar_osc.compute import extract_server_info
from nectar_osc.identity import get_project
from nectar_osc.identity import get_user
from nectar_osc.identity import get_user_emails_with_roles
from nectar_osc.util import normalize_filename
from nectar_osc.util import query_yes_no


CONF = cfg.CONF

DEFAULT_WORK_DIR = '~/.cache/os-mailout/freshdesk/'


class MailoutPrepCommand(command.Command):
    """mailout top class"""

    def get_parser(self, prog_name):
        # TODO(SC) - Could some of these command-line options be
        # made config file settings?

        parser = super().get_parser(prog_name)
        # TODO(SC) - Consider making the template either a pathname or
        # a simple name that can be looked up via some search path.
        parser.add_argument(
            '--template', help='Template pathname to use for the mailout'
        )
        # TODO(SC) - Currently a mailout directory (tempfile name) is
        # generated in the work-dir.  Consider ways to allow the operator
        # to specify (and reuse) the mailout directory.
        parser.add_argument(
            '--work-dir',
            default=os.path.expanduser(DEFAULT_WORK_DIR),
            help='Working directory for the mailout',
        )
        parser.add_argument(
            '--zone',
            action='append',
            help=(
                'Availability zone affected by outage: '
                'this option can be repeated'
            ),
        )
        parser.add_argument(
            '--ip',
            action='append',
            help=(
                'Only consider instances with specific ip address: '
                'this option can be repeated'
            ),
        )
        parser.add_argument(
            '--node',
            action='append',
            help=(
                'Only consider instances on a specific compute host/node: '
                'this option can be repeated'
            ),
        )
        parser.add_argument(
            '--image', help='Only consider instances with specific image'
        )
        parser.add_argument(
            '--status',
            default="ALL",
            help='Only consider instances with status',
        )
        parser.add_argument(
            '--user',
            help='Only consider instances owned by this user',
        )
        parser.add_argument(
            '--project',
            help='Only consider instances in this project',
        )
        parser.add_argument('--subject', help='Custom email subject')
        # TODO(SC) - there are use-cases where the '--start-time' and / or
        # '--duration' don't make sense.  These should be optional.
        parser.add_argument('--start-time', help='Outage start time')
        parser.add_argument('--duration', help='Duration of outage in hours')
        # TODO(SC) - timezone handling is broken.  Currently, the
        # '--start-time' is parsed and subsequently rendered using the host's
        # local timezone.  The '--timezone' option is simply passed in
        # the template context and treated as a text field.
        parser.add_argument(
            '--timezone',
            default="AEDT",
            help='Timezone for outage start and end',
        )
        parser.add_argument(
            '--instances-file', help='Only consider instances listed in file'
        )
        parser.add_argument(
            '--record-metadata',
            action='store_true',
            help=(
                'Record the freshdesk ticket URL in the nova instance metadata'
            ),
        )
        parser.add_argument(
            '--metadata-field',
            help=(
                'The name of the freshdesk ticket URL'
                'metadata field in the nova instance'
            ),
        )
        parser.add_argument('--limit', help='Limit the number of instances')

        return parser

    def check_args(self, args):
        if not args.start_time:
            raise Exception(
                "No --start-time=START_TIME: Please specify an outage "
                "start time; e.g. '09:00 25-06-2015'"
            )
        try:
            self.start_ts = datetime.strptime(
                args.start_time, '%H:%M %d-%m-%Y'
            )
        except ValueError:
            raise Exception(
                "Invalid --start-time: the expected date-time format is "
                "'%H:%M %d-%m-%Y'; e.g. '09:00 25-06-2015')"
            )

        if not args.duration:
            raise Exception(
                "No --duration=DURATION: Please specify outage duration "
                "in hours."
            )
        try:
            duration = int(args.duration)
            if duration < 0:
                raise Exception("Invalid --duration: cannot be negative")
            self.end_ts = self.start_ts + timedelta(hours=duration)
        except ValueError:
            raise Exception("Invalid --duration: an integer is required")

        if args.limit:
            try:
                self.limit = int(args.limit or '0')
                if self.limit <= 0:
                    raise Exception("Invalid --limit: must be >= 1")
            except ValueError:
                raise Exception("Invalid --limit: an integer is required")
        else:
            self.limit = None

        if not args.template:
            raise Exception("No template argument provided")

        if not os.path.exists(args.template):
            raise Exception("Template could not be found")

        if args.instances_file:
            if not os.path.exists(args.instances_file):
                raise Exception("Instances file could not be found")

        self.work_dir = args.work_dir
        self.template = args.template
        self.zones = args.zone
        self.ips = args.ip
        self.nodes = args.node
        self.image = args.image
        self.status = args.status
        identity = self.clients.identity
        self.user_id = get_user(identity, args.user) if args.user else None
        self.project_id = (
            get_project(identity, args.project) if args.project else None
        )
        self.subject = args.subject or self.default_subject
        self.timezone = args.timezone
        self.instances_file = args.instances_file
        self.record_metadata = args.record_metadata
        self.metadata_field = args.metadata_field

    def setup(self, args):
        self.clients = self.app.client_manager
        self.check_args(args)
        self.generator = Generator(self.template, self.subject)
        if not os.path.isdir(self.work_dir):
            os.makedirs(self.work_dir)
        self.mailout_dir = tempfile.mkdtemp(dir=self.work_dir)
        print(f"Mailout will be prepared in directory {self.mailout_dir}")
        self.count = 0

    def read_ids(self, filename):
        "Return an id iterator for file containing a list of ids"

        with open(filename) as ids:
            for id in ids:
                yield id.strip('\n')

    def generate_notification(self, key, recipients, context):
        """Generate notification and dump it to the mailout dir

        The dump includes the subject and body, the recipient list
        the context data uses for generation and a key and sequence no.
        """

        body = self.generator.render_template(context)
        subject = self.generator.render_subject(context)
        filename = normalize_filename(f"notification@{key}")
        filepath = os.path.join(self.mailout_dir, filename)
        if os.path.exists(filepath):
            raise Exception(f"Notification file {filename} already exists!")
        with open(filepath, 'w') as dump:
            content = {
                'SeqNo': self.count,
                'Key': key,
                'Subject': subject,
                'Body': body,
                'SendTo': recipients,
                'Context': dict(context),
            }
            yaml.dump(content, dump, default_flow_style=False)

        self.count += 1


class Instances(MailoutPrepCommand):
    """Prepare instance mailout

    Assemble (or read) list of instances, extract information, collate
    by project, and preparte notifications for Members and TMs for
    the project.
    """

    log = logging.getLogger(__name__ + '.Mailout.Instances')

    default_subject = "Important announcement concerning your Nectar instances"

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        # TODO(SC) refactor parser when other subcommands are implemented
        return parser

    def take_action(self, args):
        self.log.debug('take_action(%s)', args)
        self.setup(args)
        if self.instances_file:
            # TODO(SC) - implement --limit?
            instances = self.load_instances()
        else:
            instances = all_instances(
                self.clients,
                zones=self.zones,
                hosts=self.nodes,
                image_id=self.image,
                ips=self.ips,
                status=self.status,
                limit=self.limit,
                user_id=self.user_id,
                project_id=self.project_id,
            )
        self.projects = self.populate_data(instances)

        print(f"Will generate {len(self.projects)} notifications")
        for project_name, project_data in self.projects.items():
            context = {
                'start_ts': self.start_ts,
                'end_ts': self.end_ts,
                'project_name': project_name,
            }
            context.update(project_data.items())
            self.generate_notification(
                project_name, project_data['recipients'], context
            )
        print(f"Generated {self.count} notifications into {self.mailout_dir}")

    def load_instances(self):
        ids = self.read_ids(self.instances_file)
        servers = self.clients.compute.servers
        return [
            extract_server_info(self.clients, server=servers.get(id))
            for id in set(ids)
        ]

    def populate_data(self, instances):
        projects = {}
        identity = self.clients.identity
        for inst in instances:
            key = inst['project_name']
            if key in projects.keys():
                projects[key]['instances'].append(dict(inst))
            else:
                cclist = get_user_emails_with_roles(
                    identity, inst['project'], ['TenantManager', 'Member']
                )
                # Exclude projects with no valid recipients; e.g. tempest
                if cclist:
                    projects[key] = {'instances': [dict(inst)]}
                    projects[key].update({'recipients': cclist})

        return projects


# class Volumes(MailoutPrepCommand):
#     """Prepare volume mailout
#
#     Read a list of volumes, extract information, collate by project, and
#     then prpare notifications for Members and TMs for the project.
#     """
#
#     log = logging.getLogger(__name__ + '.Mailout.Volumes')
#
#     default_subject = "Important announcement concerning your Nectar volumes"
#
#     def get_parser(self, prog_name):
#         parser = super().get_parser(prog_name)
#         # TBD
#         return parser
#
#     def take_action(self, args):
#         self.log.debug('take_action(%s)', args)
#         self.setup(args)
#         raise Exception("volume mailouts not implemented yet")


# class Desktops(MailoutPrepCommand):
#     """Prepare desktop mailout
#
#     Assemble (or read) list of instances, extract information, filter
#     for desktops, collate by desktop owner and prepare notifications for
#     each owner.
#     """
#
#     log = logging.getLogger(__name__ + '.Mailout.Desktops')
#
#     default_subject = "Important announcement concerning your Nectar desktop"
#
#     def get_parser(self, prog_name):
#         parser = super().get_parser(prog_name)
#         # TBD
#         return parser
#
#     def take_action(self, args):
#         self.log.debug('take_action(%s)', args)
#         self.setup(args)
#         raise Exception("desktop mailouts not implemented yet")


class Cleanup(command.Command):
    """Clean up after a mailout"""

    log = logging.getLogger(__name__ + '.Mailout.Cleanup')

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--mailout-dir',
            help='Directory where the mailout information was written',
        )
        parser.add_argument(
            '--work-dir',
            default=os.path.expanduser(DEFAULT_WORK_DIR),
            help='Work directory for mailouts',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            default=False,
            help='Clean all mailouts',
        )
        return parser

    def check_args(self, args):
        self.mailout_dir = args.mailout_dir
        self.work_dir = args.work_dir
        self.all = args.all
        if (
            self.all
            and self.mailout_dir
            or (not self.all and not self.mailout_dir)
        ):
            raise Exception("Require one (only) of --all and --mailout-dir")
        if self.mailout_dir and not os.path.exists(self.mailout_dir):
            raise Exception(
                f"Mailout directory '{self.mailout_dir}' not found"
            )

    def take_action(self, args):
        self.check_args(args)
        self.log.debug('take_action(%s)', args)
        if self.all:
            shutil.rmtree(self.work_dir)
        else:
            shutil.rmtree(self.mailout_dir)


class Send(command.Command):
    """Perform a previously prepared mailout.

    We keep track of where we got to in the mailout by recording message
    sequence numbers in the LAST_SENT file in the mailout directory.  This
    also allows us send notifications in batches (using --limit) or do a
    trial send (using --send-to).
    """

    log = logging.getLogger(__name__ + '.Mailout.Send')

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--mailout-dir',
            help='Directory where the mailout information was saved',
        )
        parser.add_argument(
            '--send-to',
            help=(
                'Redirect notifications to this user.  This has the '
                'side-effect of suppressing updates to the LAST_SENT '
                'file.'
            ),
        )
        parser.add_argument(
            '--limit', help='Limit the number of notifications'
        )
        parser.add_argument(
            '--resume',
            action='store_true',
            default=False,
            help=(
                'Resume sending notifications after a failure.  '
                'The resumption point is determined by the LAST_SENT file'
            ),
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            default=False,
            help=('Send without asking for confirmation'),
        )
        return parser

    def check_args(self, args):
        if not args.mailout_dir:
            raise Exception("--mailout-dir <directory> option is required")
        self.mailout_dir = args.mailout_dir
        if not os.path.exists(self.mailout_dir):
            raise Exception(
                f"Mailout directory '{self.mailout_dir}' not found"
            )
        if args.limit:
            try:
                self.limit = int(args.limit)
                if self.limit < 0:
                    raise Exception("Invalid --limit: must be >= 1")
            except ValueError:
                raise Exception("Invalid --limit: an integer is required")
        else:
            self.limit = None
        self.resume = args.resume
        self.confirm = args.confirm
        self.send_to = args.send_to
        self.limit = args.limit

    def take_action(self, args):
        self.check_args(args)
        self.clients = self.app.client_manager
        self.taynac = self.clients.taynac
        self.last_sent_pathname = os.path.join(self.mailout_dir, "LAST_SENT")
        self.log.debug('take_action(%s)', args)
        (notifications, last_sent) = self.load_notifications()
        if last_sent is None:
            first = 0
        elif last_sent >= len(notifications) - 1:
            raise Exception(
                "These notifications have already been sent. "
                f"Remove file {self.last_sent_pathname} and rerun "
                "to force resending."
            )
        else:
            first = last_sent + 1
            if self.resume:
                print(f"Resuming notifications at sequence no {first}")
            else:
                raise Exception(
                    "It appears that some of the notifications have "
                    "been sent already.  Rerun with '--resume' to continue "
                    f"sending at sequence no {first}.  Remove file "
                    f"{self.last_sent_pathname} and rerun to force "
                    "resending of all notifications."
                )
        nos_to_send = len(notifications) - first
        if self.send_to:
            print(
                f"Redirecting all {nos_to_send} notifications "
                f"to {self.send_to}"
            )
        else:
            if not self.confirm:
                print(
                    f"CAUTION: this will send {nos_to_send} notifications "
                    "with each one potentially going to multiple users."
                )
                if not query_yes_no(
                    "Do you want to send them now?", default='no'
                ):
                    sys.exit(1)

        print(f"Sending notifications starting at sequence no {first}")

        sent = 0
        users = 0
        try:
            for i in range(first, len(notifications)):
                if self.limit and sent >= self.limit:
                    break
                if i not in notifications:
                    continue  # This notification has been removed.  Skip.
                notification = notifications[i]
                try:
                    self.send_notification(notification)
                except Exception:
                    print(
                        "Failed while processing notification with "
                        f"sequence no {i}"
                    )
                    raise
                sent += 1
                users += len(notification['SendTo'])
        finally:
            print(f"Sent {sent} notifications affecting {users} users")

    def send_notification(self, notification):
        if not notification['Subject']:
            raise Exception("Notification subject is empty")
        if not notification['Body']:
            raise Exception("Notification body is empty")
        if self.send_to:
            recipient = self.send_to
            cc = []
        else:
            recipient = notification['SendTo'][0]
            cc = notification['SendTo'][1:]

        self.taynac.messages.send(
            subject=notification['Subject'],
            body=notification['Body'],
            recipient=recipient,
            cc=cc,
        )
        # When using 'send_to', we are not sending "for real" so don't
        # update the LAST_SENT file
        if not self.send_to:
            with open(self.last_sent_pathname, 'w') as last_sent:
                last_sent.write(str(notification['SeqNo']))

    def load_notifications(self):
        try:
            with open(self.last_sent_pathname) as last_file:
                last_sent = int(last_file.readline())
        except FileNotFoundError:
            last_sent = None

        notifications = {}
        for filename in os.listdir(self.mailout_dir):
            if filename.startswith('notification@'):
                dumpfile = open(os.path.join(self.mailout_dir, filename))
                notification = yaml.load(dumpfile, Loader=yaml.FullLoader)
                notifications[notification['SeqNo']] = notification

        return (notifications, last_sent)


class Generator:
    def __init__(self, template, subject):
        self.template_path, self.template_name = os.path.split(template)
        self.subject_template = Template(subject)
        self.env = Environment(
            loader=FileSystemLoader(self.template_path), trim_blocks=True
        )
        self.template = self.env.get_template(self.template_name)

    def render_template(self, context):
        self.refine_context(context)
        return self.template.render(context).strip()

    def render_subject(self, context):
        '''The default behavior is to perform template expansion on the
        subject parameter.'''
        self.refine_context(context)
        return self.subject_template.render(context).strip()

    def refine_context(self, context):
        if 'start_ts' in context and 'end_ts' in context:
            start_ts = context['start_ts']
            end_ts = context['end_ts']
            duration = end_ts - start_ts
            context['days'] = duration.days
            context['hours'] = duration.seconds // 3600
