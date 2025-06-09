Mailout template catalog
========================

Documentation for the standard templates in this directory.

``zone-outage-notification.tmpl``
   Purpose: Notify an up-coming outage for one or more AZs

   Prep command: instances

   Required prep parameters: --start, --duration, --zone

   Notes: the 'actions' advice for this notification
   says that users are responsible for shutting down and
   restarting their instances.  It also recommends detaching
   volumes.

``zone-outage-notification-v2.tmpl``
   Purpose: Notify an up-coming outage for one or more AZs

   Prep command: instances

   Required prep parameters: --start, --duration, --zone

   Notes: the 'actions' advice for this notification
   says that the operators will shutdown and restart
   instances.

``host-outage-notification.tmpl``
   Purpose: Notify an up-coming outage for one or more
   compute hosts

   Prep command: instances

   Required prep parameters: --start, --duration, --host

   Notes: the 'actions' advice for this notification
   says that the operators will shutdown and restart
   instances.

``zone-planned-backplane-notification.tmpl``
   Purpose: Notify an up-coming backplane outage

   Prep command: instances

   Required prep parameters: --start, --duration, --zone

   Notes: the 'actions' advice for this notification
   says that the user should not attempt management ops.

``zone-planned-networking-notification.tmpl``
   Purpose: Notify an up-coming networing outage

   Prep command: instances

   Required prep parameters: --start, --duration, --zone

   Notes: the 'actions' advice for this notification
   says that the user should not attempt management ops.

``reboot-notification.tmpl``
   Purpose: Notify an unscheduled outage

   Prep command: instances

   Required prep parameters: --start, --duration

   Notes: the 'actions' advice for this notification
   says that the operators will restart instances
   that were previously running.

Fragments
=========

The following standard template fragments have been created for
common parts of a notification:

``affected.frag``
   Purpose: to include the table of affected instances

``signoff.frag``
   Purpose: to sign off with a generic apology and instructions
   for getting support

``schedule.frag``
   Purpose: to include the outage schedule information in a table
