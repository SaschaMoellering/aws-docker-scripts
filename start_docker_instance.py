import boto.ec2
import sys
import getopt
import time
import copy
import configuration
import docker_library

config_dict = configuration.Environment.aws_config["test"]
ami_id = config_dict["ami_id"]
ec2_key_handle = config_dict["ec2_key_handle"]
instance_type = config_dict["instance_type"]
security_groups = config_dict["security_groups"]
region = config_dict["region"]


def main(argv):
    registry = ''
    image = ''
    tag = ''
    quantity = 1

    try:
        opts, args = getopt.getopt(argv, "hr:i:t:q:", ["registry=", "image=", "tag=", "quantity="])
    except getopt.GetoptError:
        print 'start_docker_instance.py -r <registry> -i <image> -t <tag> -q <quantity>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'start_docker_instance.py -r <registry> -i <image> -t <tag> -q <quantity>'
            sys.exit()
        elif opt in ("-r", "--registry"):
            registry = arg
        elif opt in ("-i", "--image"):
            image = arg
        elif opt in ("-t", "--tag"):
            tag = arg
        elif opt in ("-q", "--quantity"):
            quantity = int(arg)
    print 'Using registry ', registry
    print 'Using image ', image
    print 'Using tag ', tag
    print 'Using quantity ', quantity

    images_list = docker_library.search_images_in_registry(registry=registry, image_name=image)

    user_data = configuration.create_user_data(registry=registry, images=images_list, tag=tag)
    print 'User-Data: \n', user_data

    start_ec2_instance(user_data, quantity, tag, image)


def start_ec2_instance(user_data, quantity, tag, image):
    conn = boto.ec2.connect_to_region(region)

    # Create a block device mapping

    dev_xvda = boto.ec2.blockdevicemapping.EBSBlockDeviceType()
    dev_xvda.size = 8  # size in Gigabytes
    dev_xvda.delete_on_termination = True
    bdm = boto.ec2.blockdevicemapping.BlockDeviceMapping()
    bdm['/dev/xvda'] = dev_xvda

    reservation = conn.run_instances(min_count=quantity,
                                     max_count=quantity,
                                     image_id=ami_id,
                                     key_name=ec2_key_handle,
                                     instance_type=instance_type,
                                     security_groups=security_groups,
                                     block_device_map=bdm,
                                     user_data=user_data,
                                     ebs_optimized=False)

    instance_ids = []
    for instance in reservation.instances:
        ec2_tag = image + '_' + tag
        instance.add_tag('application', ec2_tag)
        print "Tagging instance id %s with tag %s" % (instance.id, ec2_tag)
        instance_ids.append(instance.id)

    wait_for_instances_to_start(conn, instance_ids, copy.deepcopy(instance_ids))

    return 0


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