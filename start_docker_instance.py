import sys
import getopt
import time
import copy

import boto.ec2
import boto.ec2.networkinterface

import configuration
import docker_library

def main(argv):
    registry = ''
    image = ''
    tag = ''
    stage = ''
    dockerrun = ''
    quantity = 1

    try:
        opts, args = getopt.getopt(argv, "hr:i:t:q:s:d:", ["registry=", "image=", "tag=", "quantity=", "stage=", "dockerrun="])
    except getopt.GetoptError:
        print 'start_docker_instance.py -r <registry> -i <image> -t <tag> -q <quantity> -s <stage> -d <dockerrun>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'start_docker_instance.py -r <registry> -i <image> -t <tag> -q <quantity> -s <stage> -d <dockerrun>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-q", "--quantity"):
            quantity = int(arg)
        elif opt in ("-s", "--stage"):
            stage = arg
        elif opt in ("-d", "--dockerrun"):
            dockerrun = arg

    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using quantity ', quantity
    print 'Using stage ', stage
    print 'Using docker run command', dockerrun

    config_dict = configuration.Environment.aws_config[stage]
    ami_id = config_dict["ami_id"]
    ec2_key_handle = config_dict["ec2_key_handle"]
    instance_type = config_dict["instance_type"]
    security_groups = config_dict["security_groups"]
    region = config_dict["region"]
    subnet_id = config_dict["subnet_id"]
    public_ip_address = config_dict["public_ip_address"]
    iam_role = config_dict["iam_role"]

    images_list = docker_library.search_images_in_registry(registry=registry, image_name=image)

    user_data = configuration.create_user_data(registry=registry, images=images_list, tag=tag, stage=stage, dockerrun=dockerrun)
    print 'User-Data: \n', user_data

    id_list = start_ec2_instance(user_data, quantity, tag, image, region, subnet_id, security_groups, public_ip_address,
                                 ami_id, ec2_key_handle, instance_type, iam_role)

    sys.stdout.write(''.join(id_list))
    sys.exit(0)


def start_ec2_instance(user_data, quantity, tag, image, region, subnet_id, security_groups, public_ip_address, ami_id,
                       ec2_key_handle, instance_type, iam_role):
    conn = boto.ec2.connect_to_region(region)

    # Create a block device mapping

    dev_xvda = boto.ec2.blockdevicemapping.EBSBlockDeviceType()
    dev_xvda.size = 8  # size in Gigabytes
    dev_xvda.delete_on_termination = True
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    bdm['/dev/xvda'] = dev_xvda
    instance_ids = []
    counter = 0

    num_subnets = len(subnet_id)
    if quantity % num_subnets != 0:
        print "Can't distribute the number of instances equally between AZs"
        sys.exit(1)

    for subnet in subnet_id:

        print "Using subnet " + subnet
        interface = boto.ec2.networkinterface.NetworkInterfaceSpecification(subnet_id=subnet,
                                                                            groups=security_groups,
                                                                            associate_public_ip_address=public_ip_address)
        interfaces = boto.ec2.networkinterface.NetworkInterfaceCollection(interface)
        reservation = conn.run_instances(min_count=quantity/num_subnets,
                                         max_count=quantity/num_subnets,
                                         image_id=ami_id,
                                         key_name=ec2_key_handle,
                                         instance_type=instance_type,
                                         block_device_map=bdm,
                                         user_data=user_data,
                                         instance_profile_name=iam_role,
                                         network_interfaces=interfaces,
                                         ebs_optimized=False)

        for instance in reservation.instances:
            ec2_tag = image + '_' + tag
            instance.add_tag('application', ec2_tag)
            print "Tagging instance id %s with tag %s" % (instance.id, ec2_tag)
            instance_ids.append(instance.id)

        wait_for_instances_to_start(conn, instance_ids, copy.deepcopy(instance_ids))

        counter += 1

    return instance_ids


def wait_for_instances_to_start(conn, instance_ids, pending_ids):
    """Loop through all pending instance ids waiting for them to start.
        If an instance is running, remove it from pending_ids.
        If there are still pending requests, sleep and check again in 10 seconds.
        Only return when all instances are running."""
    reservations = conn.get_all_instances(instance_ids=pending_ids)
    for reservation in reservations:
        for instance in reservation.instances:
            if instance.state == 'running':
                print "instance `{" + instance.id + "}` running!"
                pending_ids.pop(pending_ids.index(instance.id))
            else:
                print "instance `{" + instance.id + "}` starting..."
    if len(pending_ids) == 0:
        print "all instances started!"
    else:
        time.sleep(10)
        wait_for_instances_to_start(conn, instance_ids, pending_ids)


if __name__ == "__main__":
    main(sys.argv[1:])