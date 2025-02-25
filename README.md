# Nectar Openstack Client Plugin

Provides some helpers for nectar cloud.

## Commands

### Security command
These can be used to take down an instance due to a security issue
 openstack nectar security instance lock
 openstack nectar security instance unlock
 openstack nectar security instance delete

### Enhanced commands
Show extra info to a standard "show" command in openstack client
 openstack nectar server show
 openstack nectar server securitygroups

### Flavor commands
Include service unit cost as part of flavor list
 openstack nectar flavor list

### Mailout commands
 openstack nectar mailout instances
 openstack nectar mailout cleanup
 openstack nectar mailout send
