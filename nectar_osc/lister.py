from osc_lib import utils as osc_utils

def show_instance(clients, instance_id):
    result = clients.compute.servers.get(instance_id)
    columns = ['id', 'name']
    return( columns, (osc_utils.get_item_properties(result, columns)))

def show_sg_groups(clients, instance_id):
    ports = clients.network.ports(device_id=instance_id)
    sg_ids = []; rules = []; result = []
    for p in ports:
        for sg in p.security_group_ids:
            sg_ids.append(sg)
    return(sg_ids)
